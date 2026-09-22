"""
GENEX ASV - Manual Mode Controller
Coordinates RC input, zero-throttle arming interlock, differential motor mixing,
E-stop safety integration, and telemetry publication.
"""

import logging
import threading
import time
from typing import Optional, Tuple

from backend.config import settings
from backend.telemetry.state import ManualControlStatus, MotorStatus
from backend.rc.reader import rc_reader
from backend.control.motor_driver import MotorController
from backend.control.latency_tracker import latency_tracker
from backend.safety.safety_manager import safety_manager

logger = logging.getLogger("genex.control.manual_controller")


class ManualModeController:
    """
    Central controller for FlySky Manual Mode.
    Operates an independent 50 Hz control loop and acts as the single authority
    on manual control state and motor command computation.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.motor_controller = MotorController(
            throttle_accel_rate=settings.MANUAL_THROTTLE_ACCEL_RATE,
            throttle_decel_rate=settings.MANUAL_THROTTLE_DECEL_RATE,
            steering_accel_rate=settings.MANUAL_STEERING_ACCEL_RATE,
            steering_decel_rate=settings.MANUAL_STEERING_DECEL_RATE,
            motors_enabled=settings.MOTORS_ENABLED,
        )

        self._manual_status = ManualControlStatus(
            state="DISCONNECTED",
            is_active=False,
            control_available=False,
            throttle_zero_confirmed=False,
            lockout_reason="STARTING",
            motors_inhibited=True,
        )

        self._motor_status = MotorStatus(
            left_output=0.0,
            right_output=0.0,
            left_pwm_us=settings.PWM_NEUTRAL_US,
            right_pwm_us=settings.PWM_NEUTRAL_US,
            left_percent=0.0,
            right_percent=0.0,
            neutralized=True,
            motors_enabled=settings.MOTORS_ENABLED,
        )

    def start(self) -> None:
        """Start the manual controller thread and register safety callbacks."""
        with self._lock:
            if self._running:
                logger.warning("ManualModeController is already running.")
                return

            self._running = True

            # Register emergency stop hook with safety_manager
            safety_manager.register_motor_stop_callback(self.emergency_neutral_stop)

            self._thread = threading.Thread(
                target=self._control_loop,
                name="ManualControllerThread",
                daemon=True
            )
            self._thread.start()
            logger.info("ManualModeController thread started (50 Hz control loop).")

    def stop(self) -> None:
        """Clean shutdown handler."""
        with self._lock:
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        self.motor_controller.shutdown()
        logger.info("ManualModeController stopped.")

    def emergency_neutral_stop(self) -> None:
        """Registered callback for SafetyManager to immediately neutralize motor targets."""
        with self._lock:
            self.motor_controller.immediate_neutral_stop()
            self._manual_status.state = "LOCKED_OUT"
            self._manual_status.is_active = False
            self._manual_status.control_available = False
            self._manual_status.lockout_reason = "ESTOP_ACTIVE"

            self._motor_status = MotorStatus(
                left_output=0.0,
                right_output=0.0,
                left_pwm_us=settings.PWM_NEUTRAL_US,
                right_pwm_us=settings.PWM_NEUTRAL_US,
                left_percent=0.0,
                right_percent=0.0,
                neutralized=True,
                motors_enabled=settings.MOTORS_ENABLED,
                safety_override_active=True,
                final_pwm_left=settings.PWM_NEUTRAL_US,
                final_pwm_right=settings.PWM_NEUTRAL_US,
            )
        logger.warning("ManualModeController received EMERGENCY STOP: Motors snapped to Neutral.")

    def _control_loop(self) -> None:
        """Event-driven real-time control loop with 50 Hz fallback."""
        loop_interval = 1.0 / settings.RC_LOOP_HZ
        last_t = time.monotonic()
        rc_event = getattr(rc_reader, "frame_ready_event", None)

        while self._running:
            if rc_event is not None:
                rc_event.wait(timeout=loop_interval)
                rc_event.clear()
            else:
                time.sleep(loop_interval)

            if not self._running:
                break

            now = time.monotonic()
            dt = max(0.001, min(0.1, now - last_t))
            last_t = now

            try:
                # 1. Fetch latest processed RC inputs and pipeline timestamps
                norm_str, norm_thr, ch5_active, thr_zero, is_healthy, frame_age = rc_reader.get_control_inputs()
                t_recv, t_dec, t_rc = rc_reader.get_latency_timestamps()
                rc_status_snap = rc_reader.get_status()
                raw_thr_us = rc_status_snap.ch3_raw
                raw_str_us = rc_status_snap.ch1_raw

                # 2. Check system safety state
                estop_active = safety_manager.is_estop_active()

                with self._lock:
                    actual_thr = 0.0
                    actual_str = 0.0

                    # Priority 1: E-stop condition (IMMEDIATE SNAP TO NEUTRAL, NEVER RAMPED)
                    if estop_active:
                        self.motor_controller.is_armed = False
                        self.motor_controller.require_throttle_zero = True
                        self.motor_controller.immediate_neutral_stop()
                        state = "LOCKED_OUT"
                        lockout_reason = "ESTOP_ACTIVE"
                        is_active = False
                        avail = False
                        thr_zero_confirmed = False
                        left_out, right_out = 0.0, 0.0
                        left_pwm, right_pwm = settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US

                    # Priority 2: RC Failsafe / Signal Loss / Disconnected (IMMEDIATE SNAP TO NEUTRAL, NEVER RAMPED)
                    elif not is_healthy:
                        self.motor_controller.is_armed = False
                        self.motor_controller.require_throttle_zero = True
                        self.motor_controller.immediate_neutral_stop()
                        has_had_frames = rc_status_snap.valid_frames > 0
                        state = "FAILSAFE" if (frame_age < 5.0 and has_had_frames) else "DISCONNECTED"
                        lockout_reason = "RC_SIGNAL_LOST" if state == "FAILSAFE" else "NO_RC_SIGNAL"
                        is_active = False
                        avail = False
                        thr_zero_confirmed = False
                        left_out, right_out = 0.0, 0.0
                        left_pwm, right_pwm = settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US

                    # Priority 3: Healthy RC Signal & Inactive E-Stop
                    else:
                        avail = True
                        thr_zero_confirmed = thr_zero

                        if ch5_active:
                            # Evaluate Zero-Throttle Arming Interlock
                            armed = self.motor_controller.update_arming_state(ch5_active=True, is_throttle_zero=thr_zero)
                            if armed:
                                state = "ACTIVE"
                                lockout_reason = None
                                is_active = True
                                # Process differential thrust with end-to-end timing
                                t_mc = time.monotonic()
                                left_out, right_out, left_pwm, right_pwm, actual_thr, actual_str = (
                                    self.motor_controller.process_and_output(norm_thr, norm_str, dt)
                                )
                                t_pca = time.monotonic()
                                if t_recv > 0.0:
                                    latency_tracker.record_sample(
                                        t_frame_recv=t_recv,
                                        t_frame_decoded=t_dec,
                                        t_rcreader_update=t_rc,
                                        t_manual_ctrl=t_mc,
                                        t_mixer=t_mc,
                                        t_motor_ctrl=t_mc,
                                        t_pca_write=t_pca,
                                    )
                            else:
                                state = "LOCKED_OUT"
                                lockout_reason = "THROTTLE_NOT_ZERO"
                                is_active = False
                                left_out, right_out = 0.0, 0.0
                                left_pwm, right_pwm = settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US
                        else:
                            # CH5 is OFF: Standby mode (IMMEDIATE SNAP TO NEUTRAL, NEVER RAMPED)
                            self.motor_controller.update_arming_state(ch5_active=False, is_throttle_zero=thr_zero)
                            state = "STANDBY"
                            lockout_reason = "CH5_SWITCH_OFF"
                            is_active = False
                            left_out, right_out = 0.0, 0.0
                            left_pwm, right_pwm = settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US

                    # Compute unramped target differential values for debugging comparison
                    t_left, t_right = self.motor_controller.mixer.mix(norm_thr, norm_str)

                    # Update Telemetry Models
                    self._manual_status = ManualControlStatus(
                        state=state,
                        is_active=is_active,
                        control_available=avail,
                        throttle_zero_confirmed=thr_zero_confirmed,
                        lockout_reason=lockout_reason,
                        motors_inhibited=not settings.MOTORS_ENABLED or not is_active,
                    )

                    self._motor_status = MotorStatus(
                        left_output=round(left_out, 4),
                        right_output=round(right_out, 4),
                        left_pwm_us=round(left_pwm, 1),
                        right_pwm_us=round(right_pwm, 1),
                        left_percent=round(abs(left_out) * 100.0, 1),
                        right_percent=round(abs(right_out) * 100.0, 1),
                        neutralized=(left_out == 0.0 and right_out == 0.0),
                        motors_enabled=settings.MOTORS_ENABLED,
                        safety_override_active=estop_active,
                        requested_throttle=round(norm_thr, 4),
                        requested_steering=round(norm_str, 4),
                        raw_throttle_us=raw_thr_us,
                        raw_steering_us=raw_str_us,
                        target_throttle=round(norm_thr, 4),
                        target_steering=round(norm_str, 4),
                        actual_throttle=round(actual_thr, 4),
                        actual_steering=round(actual_str, 4),
                        target_left=round(t_left, 4),
                        target_right=round(t_right, 4),
                        final_pwm_left=round(left_pwm, 1),
                        final_pwm_right=round(right_pwm, 1),
                    )

            except Exception as exc:
                logger.error("Error in ManualModeController control loop: %s", exc)

    def get_manual_status(self) -> ManualControlStatus:
        """Thread-safe snapshot of manual control status."""
        with self._lock:
            return self._manual_status.model_copy()

    def get_motor_status(self) -> MotorStatus:
        """Thread-safe snapshot of motor mixer status."""
        with self._lock:
            return self._motor_status.model_copy()


# Global singleton instance
manual_controller = ManualModeController()
