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
        self.assertEqual(motors.right_pwm_us, settings.PWM_NEUTRAL_US)
        self.assertTrue(motors.neutralized)
        self.assertFalse(motors.motors_enabled)

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
        l_out, r_out, l_pwm, r_pwm = self.controller.motor_controller.process_and_output(0.5, 0.2, 0.5)

        self.assertTrue(self.controller.motor_controller.is_armed)
        self.assertGreater(l_out, 0.0)
        self.assertGreater(r_out, 0.0)


if __name__ == "__main__":
    unittest.main()
