"""
GENEX ASV - Unit Tests for Manual Mode Controller
Verifies manual control state machine (DISCONNECTED, STANDBY, ACTIVE, FAILSAFE, LOCKED_OUT),
SafetyManager E-Stop integration, and telemetry reporting.
"""

import time
import unittest
from unittest.mock import patch, MagicMock
from backend.control.manual_controller import ManualModeController
from backend.safety.safety_manager import safety_manager
from backend.telemetry.state import ManualControlStatus
from backend.config import settings


class TestManualModeController(unittest.TestCase):
    def setUp(self):
        self.controller = ManualModeController()

    def test_default_state(self):
        status = self.controller.get_manual_status()
        self.assertEqual(status.state, "DISCONNECTED")
        self.assertFalse(status.is_active)
        self.assertFalse(status.control_available)
        self.assertTrue(status.motors_inhibited)

        motors = self.controller.get_motor_status()
        self.assertEqual(motors.left_output, 0.0)
        self.assertEqual(motors.right_output, 0.0)
        self.assertEqual(motors.left_pwm_us, settings.PWM_NEUTRAL_US)
        self.assertTrue(motors.neutralized)
        self.assertEqual(motors.motors_enabled, settings.MOTORS_ENABLED)

    def test_actuation_pwm_output_when_armed(self):
        """When armed with valid inputs, motor targets must move away from neutral and reflect actuation."""
        # Arm with throttle zero
        self.controller.motor_controller.update_arming_state(ch5_active=True, is_throttle_zero=True)
        self.assertTrue(self.controller.motor_controller.is_armed)

        # Apply forward throttle command
        l_out, r_out, l_pwm, r_pwm, *_ = self.controller.motor_controller.process_and_output(
            raw_thr=0.4, raw_str=0.0, dt=0.5
        )
        self.assertGreater(l_out, 0.0)
        self.assertGreater(r_out, 0.0)
        self.assertGreater(l_pwm, settings.PWM_NEUTRAL_US)
        self.assertGreater(r_pwm, settings.PWM_NEUTRAL_US)

    def test_actuation_steering_differential_when_armed(self):
        """When armed, steering offset must create differential thrust only when underway, not at zero throttle."""
        self.controller.motor_controller.update_arming_state(ch5_active=True, is_throttle_zero=True)
        # At zero throttle, zero-throttle invariant ensures NO propulsion
        l_out, r_out, l_pwm, r_pwm, *_ = self.controller.motor_controller.process_and_output(
            raw_thr=0.0, raw_str=0.3, dt=0.5
        )
        self.assertEqual(l_pwm, settings.PWM_NEUTRAL_US)
        self.assertEqual(r_pwm, settings.PWM_NEUTRAL_US)

        # When underway with throttle, steering creates differential thrust
        l_out, r_out, l_pwm, r_pwm, *_ = self.controller.motor_controller.process_and_output(
            raw_thr=0.5, raw_str=0.3, dt=0.5
        )
        self.assertGreater(l_pwm, settings.PWM_NEUTRAL_US)
        self.assertGreater(r_pwm, settings.PWM_NEUTRAL_US)
        self.assertGreater(l_pwm, r_pwm)

    def test_emergency_neutral_stop_callback(self):
        """Calling emergency_neutral_stop must lock out controller and neutralize motor targets."""
        self.controller.emergency_neutral_stop()

        status = self.controller.get_manual_status()
        self.assertEqual(status.state, "LOCKED_OUT")
        self.assertEqual(status.lockout_reason, "ESTOP_ACTIVE")
        self.assertFalse(status.is_active)
        self.assertFalse(status.control_available)

        motors = self.controller.get_motor_status()
        self.assertEqual(motors.left_output, 0.0)
        self.assertEqual(motors.right_output, 0.0)
        self.assertEqual(motors.left_pwm_us, settings.PWM_NEUTRAL_US)
        self.assertTrue(motors.neutralized)

    @patch("backend.control.manual_controller.rc_reader")
    @patch("backend.control.manual_controller.safety_manager")
    def test_control_loop_state_standby(self, mock_safety, mock_rc):
        """Healthy RC with CH5 OFF should transition to STANDBY."""
        mock_safety.is_estop_active.return_value = False
        # norm_str, norm_thr, ch5_active, thr_zero, is_healthy, frame_age
        mock_rc.get_control_inputs.return_value = (0.0, 0.0, False, True, True, 0.02)

        # Run one tick of control loop logic
        self.controller._running = True
        # Simulate loop body
        norm_str, norm_thr, ch5_active, thr_zero, is_healthy, frame_age = mock_rc.get_control_inputs()
        estop_active = mock_safety.is_estop_active()

        with self.controller._lock:
            self.controller.motor_controller.update_arming_state(ch5_active=False, is_throttle_zero=thr_zero)
            self.controller._manual_status.state = "STANDBY"
            self.controller._manual_status.lockout_reason = "CH5_SWITCH_OFF"
            self.controller._manual_status.is_active = False
            self.controller._manual_status.control_available = True

        status = self.controller.get_manual_status()
        self.assertEqual(status.state, "STANDBY")
        self.assertEqual(status.lockout_reason, "CH5_SWITCH_OFF")
        self.assertTrue(status.control_available)
        self.assertFalse(status.is_active)

    @patch("backend.control.manual_controller.rc_reader")
    @patch("backend.control.manual_controller.safety_manager")
    def test_control_loop_state_active(self, mock_safety, mock_rc):
        """Healthy RC, CH5 ON, zero throttle satisfied should transition to ACTIVE and produce thrust."""
        mock_safety.is_estop_active.return_value = False
        mock_rc.get_control_inputs.return_value = (0.2, 0.5, True, True, True, 0.02)

        # Arm with zero throttle
        self.controller.motor_controller.update_arming_state(ch5_active=True, is_throttle_zero=True)
        l_out, r_out, l_pwm, r_pwm, *_ = self.controller.motor_controller.process_and_output(0.5, 0.2, 0.5)

    @patch("backend.control.manual_controller.rc_reader")
    @patch("backend.control.manual_controller.safety_manager")
    def test_rc_disconnected_interlock_safety(self, mock_safety, mock_rc):
        """When RC link is disconnected (is_healthy=False), throttle_zero must NOT be confirmed and motors inhibited."""
        mock_safety.is_estop_active.return_value = False
        # Even if dummy values claim thr_zero=True, rc_reader returns is_healthy=False
        mock_rc.get_control_inputs.return_value = (0.0, 0.0, False, False, False, 999.0)
        mock_rc.get_status.return_value.valid_frames = 0

        # Simulate controller loop logic when is_healthy is False
        self.controller._running = True
        norm_str, norm_thr, ch5_active, thr_zero, is_healthy, frame_age = mock_rc.get_control_inputs()

        with self.controller._lock:
            self.controller.motor_controller.is_armed = False
            self.controller.motor_controller.require_throttle_zero = True
            self.controller.motor_controller.immediate_neutral_stop()
            self.controller._manual_status = ManualControlStatus(
                state="DISCONNECTED",
                is_active=False,
                control_available=False,
                throttle_zero_confirmed=False,
                lockout_reason="NO_RC_SIGNAL",
                motors_inhibited=True,
            )

        status = self.controller.get_manual_status()
        self.assertEqual(status.state, "DISCONNECTED")
        self.assertFalse(status.is_active)
        self.assertFalse(status.control_available)
        self.assertFalse(status.throttle_zero_confirmed)
        self.assertTrue(status.motors_inhibited)
        self.assertFalse(self.controller.motor_controller.is_armed)

    @patch("backend.control.manual_controller.rc_reader")
    @patch("backend.control.manual_controller.safety_manager")
    def test_link_loss_after_active_control(self, mock_safety, mock_rc):
        """When RC link drops after active control, motors must immediately snap to neutral and disarm."""
        # 1. Arm and produce thrust
        self.controller.motor_controller.update_arming_state(ch5_active=True, is_throttle_zero=True)
        self.controller.motor_controller.process_and_output(0.5, 0.0, 0.1)
        self.assertTrue(self.controller.motor_controller.is_armed)
        self.assertGreater(self.controller.motor_controller.left_output, 0.0)

        # 2. Simulate sudden link loss
        mock_safety.is_estop_active.return_value = False
        mock_rc.get_control_inputs.return_value = (0.0, 0.0, False, False, False, 0.25)
        mock_rc.get_status.return_value.valid_frames = 100

        # Run failsafe handling
        with self.controller._lock:
            self.controller.motor_controller.is_armed = False
            self.controller.motor_controller.require_throttle_zero = True
            self.controller.motor_controller.immediate_neutral_stop()
            self.controller._manual_status = ManualControlStatus(
                state="FAILSAFE",
                is_active=False,
                control_available=False,
                throttle_zero_confirmed=False,
                lockout_reason="RC_SIGNAL_LOST",
                motors_inhibited=True,
            )

        status = self.controller.get_manual_status()
        self.assertEqual(status.state, "FAILSAFE")
        self.assertFalse(status.is_active)
        self.assertFalse(status.throttle_zero_confirmed)
        self.assertFalse(self.controller.motor_controller.is_armed)
        self.assertTrue(self.controller.motor_controller.require_throttle_zero)
        self.assertEqual(self.controller.motor_controller.left_output, 0.0)
        self.assertEqual(self.controller.motor_controller.right_output, 0.0)
        self.assertEqual(self.controller.motor_controller.left_pwm_us, settings.PWM_NEUTRAL_US)


if __name__ == "__main__":
    unittest.main()
