"""
GENEX ASV - Safety Manager & IR Obstacle Detection Subsystem
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Callable

from backend.config import settings
from backend.telemetry.state import SafetyStatus

logger = logging.getLogger("genex.safety")


class SafetyManager:
    """
    Singleton Safety Manager for GENEX ASV.
    Exclusively manages BCM GPIO17 for the LM393 digital IR obstacle sensor.
    Implements a fail-safe, latched Obstacle E-stop state machine for semi-autonomous mode.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._device = None
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Hardware & sensor state
        self._ir_sensor_connected: bool = False
        self._ir_gpio_level: int = 1  # 1 = HIGH (3.3V), 0 = LOW (0V)
        self._ir_obstacle_detected: bool = False
        self._last_change_timestamp: Optional[str] = None

        # Safety E-stop state machine
        self._obstacle_estop_active: bool = False
        self._obstacle_estop_latched: bool = False
        self._obstacle_estop_reason: Optional[str] = None

        # External hooks / callbacks
        self._motor_stop_callback: Optional[Callable[[], None]] = None
        self._mode_revert_callback: Optional[Callable[[], None]] = None
        self._get_operating_mode_callback: Optional[Callable[[], str]] = None

    def register_motor_stop_callback(self, cb: Callable[[], None]) -> None:
        """Register hook to stop propulsion / set motors to neutral."""
        self._motor_stop_callback = cb

    def register_mode_revert_callback(self, cb: Callable[[], None]) -> None:
        """Register hook to force operating mode to manual."""
        self._mode_revert_callback = cb

    def register_get_operating_mode_callback(self, cb: Callable[[], str]) -> None:
        """Register hook to query current ASV operating mode."""
        self._get_operating_mode_callback = cb

    def _get_current_mode(self) -> str:
        if self._get_operating_mode_callback:
            try:
                return self._get_operating_mode_callback()
            except Exception as e:
                logger.error("Error invoking get_operating_mode callback: %s", e)
        return "manual"

    def _execute_motor_stop(self) -> None:
        """Execute motor stop hook to neutralize ASV propulsion safely."""
        if self._motor_stop_callback:
            try:
                self._motor_stop_callback()
                logger.info("Executed motor stop / neutral command via registered hook.")
            except Exception as e:
                logger.error("Error invoking motor stop callback: %s", e)
        else:
            logger.info("Motor stop hook executed (no external motor controller attached).")

    def _execute_mode_revert(self) -> None:
        """Force operating mode to manual upon safety trip."""
        if self._mode_revert_callback:
            try:
                self._mode_revert_callback()
                logger.warning("Safety manager forced ASV operating mode to MANUAL.")
            except Exception as e:
                logger.error("Error invoking mode revert callback: %s", e)

    def start(self) -> None:
        """Start the safety manager and initialize GPIO17 reader."""
        with self._lock:
            if self._running:
                logger.warning("SafetyManager is already running.")
                return

            self._running = True
            self._init_gpio()

            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="SafetyMonitorThread",
                daemon=True
            )
            self._monitor_thread.start()
            logger.info("SafetyManager started on BCM GPIO%d (active_low=%s, debounce=%.3fs).",
                        settings.IR_SENSOR_PIN, settings.IR_ACTIVE_LOW, settings.IR_DEBOUNCE_SEC)

    def stop(self) -> None:
        """Stop the safety monitor and release GPIO17."""
        with self._lock:
            if not self._running:
                return
            logger.info("Stopping SafetyManager...")
            self._running = False

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)

        with self._lock:
            if self._device is not None:
                try:
                    self._device.close()
                except Exception as e:
                    logger.error("Error closing GPIO device: %s", e)
                finally:
                    self._device = None
            self._ir_sensor_connected = False
            logger.info("SafetyManager stopped and GPIO17 released.")

    def _init_gpio(self) -> None:
        """Initialize the GPIO device using gpiozero with debouncing."""
        if not settings.ENABLE_IR_SENSOR:
            logger.info("IR obstacle sensor is disabled in configuration.")
            self._ir_sensor_connected = False
            return

        try:
            from gpiozero import DigitalInputDevice
            # BCM GPIO17 with internal pull-up and hardware/software debouncing
            self._device = DigitalInputDevice(
                pin=settings.IR_SENSOR_PIN,
                pull_up=True,
                bounce_time=settings.IR_DEBOUNCE_SEC
            )
            self._ir_sensor_connected = True
            logger.info("Successfully acquired GPIO%d via %s.",
                        settings.IR_SENSOR_PIN, self._device.pin_factory.__class__.__name__)
        except Exception as e:
            logger.warning("Could not initialize physical GPIO%d device (%s). Running in simulation/mock fallback.",
                           settings.IR_SENSOR_PIN, e)
            self._device = None
            self._ir_sensor_connected = False

    def _read_physical_pin_level(self) -> Optional[int]:
        """
        Read the actual electrical logic level on the pin.
        Returns 1 for HIGH (3.3V) and 0 for LOW (GND/0V).
        """
        if self._device is None:
            return None
        try:
            # pin.state is boolean True for 3.3V HIGH, False for GND LOW
            state = getattr(self._device.pin, "state", None)
            if state is not None:
                return 1 if bool(state) else 0
            # Fallback if pin.state not available
            return 1 if self._device.value == 0 else 0
        except Exception as e:
            logger.error("Error reading GPIO pin level: %s", e)
            return None

    def _monitor_loop(self) -> None:
        """Continuous debounced monitoring loop (runs at ~50 Hz)."""
        poll_interval = 0.020  # 20 ms
        last_raw_level = None

        while self._running:
            try:
                raw_level = self._read_physical_pin_level()
                now_iso = datetime.now(timezone.utc).isoformat()

                with self._lock:
                    if raw_level is not None:
                        self._ir_sensor_connected = True
                        self._ir_gpio_level = raw_level

                        # Determine obstacle detection based on configured active logic
                        if settings.IR_ACTIVE_LOW:
                            is_obstacle = (raw_level == 0)
                        else:
                            is_obstacle = (raw_level == 1)

                        if raw_level != last_raw_level:
                            self._last_change_timestamp = now_iso
                            last_raw_level = raw_level
                            logger.debug("GPIO%d level changed to %d (obstacle=%s)",
                                         settings.IR_SENSOR_PIN, raw_level, is_obstacle)

                        self._ir_obstacle_detected = is_obstacle

                        # Safety Trip Evaluation:
                        # Only trigger E-stop when obstacle is detected during semi-autonomous navigation
                        current_mode = self._get_current_mode()
                        if is_obstacle and current_mode == "semi_autonomous":
                            if not self._obstacle_estop_active:
                                self._trigger_estop_internal(reason="IR_OBSTACLE_DETECTED")
                    else:
                        # Sensor hardware read failure / disconnection
                        if self._ir_sensor_connected:
                            logger.error("IR Sensor read failure detected! Marking sensor disconnected.")
                            self._ir_sensor_connected = False
                            # Safe failure policy: if in semi_autonomous, trip safety stop
                            if self._get_current_mode() == "semi_autonomous" and not self._obstacle_estop_active:
                                self._trigger_estop_internal(reason="IR_SENSOR_FAULT")

                time.sleep(poll_interval)
            except Exception as e:
                logger.error("Error in SafetyManager monitor loop: %s", e)
                time.sleep(0.5)

    def _trigger_estop_internal(self, reason: str) -> None:
        """Internal helper to latch E-stop, stop propulsion, and force manual mode."""
        self._obstacle_estop_active = True
        self._obstacle_estop_latched = True
        self._obstacle_estop_reason = reason
        logger.critical(">>> OBSTACLE E-STOP TRIGGERED! Reason: %s <<<", reason)
        # Execute failsafe actions outside the lock to prevent deadlocks
        threading.Thread(target=self._execute_failsafe_actions, daemon=True).start()

    def _execute_failsafe_actions(self) -> None:
        self._execute_motor_stop()
        self._execute_mode_revert()

    def trigger_estop(self, reason: str = "MANUAL_ESTOP") -> None:
        """Manually trigger the E-stop safety state."""
        with self._lock:
            self._trigger_estop_internal(reason)

    def reset_estop(self) -> dict:
        """
        Operator-commanded reset of the Obstacle E-stop.
        Strict Safety Contract:
        1. Checks whether an obstacle is STILL detected. If yes, strictly rejects reset.
        2. If sensor is disconnected / faulted, strictly rejects reset.
        3. Clears E-stop latch and reason.
        4. Vehicle REMAINS in manual mode (never resumes autonomous navigation automatically).
        """
        with self._lock:
            # Refresh live reading if device is active
            raw = self._read_physical_pin_level()
            if raw is not None:
                self._ir_gpio_level = raw
                if settings.IR_ACTIVE_LOW:
                    self._ir_obstacle_detected = (raw == 0)
                else:
                    self._ir_obstacle_detected = (raw == 1)

            if not self._ir_sensor_connected:
                raise ValueError("Cannot reset Obstacle E-stop: IR sensor is disconnected or faulted.")

            if self._ir_obstacle_detected:
                raise ValueError("Cannot reset Obstacle E-stop: IR obstacle is still detected in path.")

            if not self._obstacle_estop_active and not self._obstacle_estop_latched:
                return {
                    "status": "ok",
                    "message": "Obstacle E-stop is not currently latched."
                }

            # Clear safety latch
            self._obstacle_estop_active = False
            self._obstacle_estop_latched = False
            self._obstacle_estop_reason = None
            logger.info("Obstacle E-stop successfully reset by operator. Vehicle remains in MANUAL mode.")

            return {
                "status": "ok",
                "message": "Obstacle E-stop reset successfully. Propulsion unlocked in MANUAL mode."
            }

    def is_estop_active(self) -> bool:
        """Returns True if the Obstacle E-stop is currently active/latched."""
        with self._lock:
            return self._obstacle_estop_active

    def is_obstacle_detected(self) -> bool:
        """Returns True if an obstacle is currently detected."""
        with self._lock:
            return self._ir_obstacle_detected

    def get_status(self) -> SafetyStatus:
        """Return a snapshot of current safety state."""
        with self._lock:
            # Reset is allowed only if obstacle is NOT currently detected and sensor is connected
            reset_allowed = self._ir_sensor_connected and not self._ir_obstacle_detected
            return SafetyStatus(
                ir_sensor_connected=self._ir_sensor_connected,
                ir_obstacle_detected=self._ir_obstacle_detected,
                ir_gpio_level=self._ir_gpio_level,
                ir_last_change_timestamp=self._last_change_timestamp,
                obstacle_estop_active=self._obstacle_estop_active,
                obstacle_estop_reason=self._obstacle_estop_reason,
                obstacle_estop_latched=self._obstacle_estop_latched,
                reset_allowed=reset_allowed,
                detection_range_status="Proximity threshold only (potentiometer adjusted)"
            )

    # Simulation / test helpers
    def _simulate_gpio_level(self, level: int) -> None:
        """Helper for unit tests to inject pin levels in mock mode."""
        with self._lock:
            self._ir_sensor_connected = True
            self._ir_gpio_level = level
            if settings.IR_ACTIVE_LOW:
                self._ir_obstacle_detected = (level == 0)
            else:
                self._ir_obstacle_detected = (level == 1)
            self._last_change_timestamp = datetime.now(timezone.utc).isoformat()
            if self._ir_obstacle_detected and self._get_current_mode() == "semi_autonomous":
                if not self._obstacle_estop_active:
                    self._trigger_estop_internal(reason="IR_OBSTACLE_DETECTED")


# Singleton instance
safety_manager = SafetyManager()
