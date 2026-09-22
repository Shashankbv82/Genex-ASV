"""
GENEX ASV - Unit Tests for SafetyManager & IR Obstacle State Machine (unittest)
"""

import time
import unittest
from unittest.mock import MagicMock
from backend.safety.safety_manager import SafetyManager
from backend.config import settings


class TestSafetyManager(unittest.TestCase):
    def setUp(self):
        self.sm = SafetyManager()
        # Mock settings to ensure known test baseline
        settings.IR_ACTIVE_LOW = True
        settings.ENABLE_IR_SENSOR = False  # Keep in software simulation mode
        self.sm._ir_sensor_connected = True
        self.sm._ir_gpio_level = 1  # 1 = HIGH (clear)
        self.sm._ir_obstacle_detected = False
        self.sm._obstacle_estop_active = False
        self.sm._obstacle_estop_latched = False
        self.sm._obstacle_estop_reason = None

    def tearDown(self):
        self.sm.stop()

    def test_default_state(self):
        status = self.sm.get_status()
        self.assertTrue(status.ir_sensor_connected)
        self.assertEqual(status.ir_gpio_level, 1)
        self.assertFalse(status.ir_obstacle_detected)
        self.assertFalse(status.obstacle_estop_active)
        self.assertFalse(status.obstacle_estop_latched)
        self.assertIsNone(status.obstacle_estop_reason)
        self.assertTrue(status.reset_allowed)
        self.assertIn("Proximity threshold only", status.detection_range_status)

    def test_semi_autonomous_obstacle_triggers_estop(self):
        motor_stop_mock = MagicMock()
        mode_revert_mock = MagicMock()

        self.sm.register_motor_stop_callback(motor_stop_mock)
        self.sm.register_mode_revert_callback(mode_revert_mock)
        self.sm.register_get_operating_mode_callback(lambda: "semi_autonomous")

        # Simulate obstacle detection: Pin drops to 0 (LOW / GND)
        self.sm._simulate_gpio_level(0)

        # Wait brief moment for failsafe thread
        time.sleep(0.05)

        status = self.sm.get_status()
        self.assertTrue(status.ir_obstacle_detected)
        self.assertTrue(status.obstacle_estop_active)
        self.assertTrue(status.obstacle_estop_latched)
        self.assertEqual(status.obstacle_estop_reason, "IR_OBSTACLE_DETECTED")
        self.assertFalse(status.reset_allowed)

        # Verify motor stop and mode revert callbacks were executed
        motor_stop_mock.assert_called_once()
        mode_revert_mock.assert_called_once()

    def test_manual_mode_obstacle_does_not_trip_estop(self):
        motor_stop_mock = MagicMock()
        mode_revert_mock = MagicMock()

        self.sm.register_motor_stop_callback(motor_stop_mock)
        self.sm.register_mode_revert_callback(mode_revert_mock)
        self.sm.register_get_operating_mode_callback(lambda: "manual")

        # Simulate obstacle detection in manual mode
        self.sm._simulate_gpio_level(0)

        status = self.sm.get_status()
        self.assertTrue(status.ir_obstacle_detected)
        # In manual mode, operator retains control; estop does not auto-trip
        self.assertFalse(status.obstacle_estop_active)
        self.assertFalse(status.obstacle_estop_latched)
        motor_stop_mock.assert_not_called()
        mode_revert_mock.assert_not_called()

    def test_latch_persistence(self):
        self.sm.register_get_operating_mode_callback(lambda: "semi_autonomous")

        # 1. Trigger obstacle
        self.sm._simulate_gpio_level(0)
        self.assertTrue(self.sm.is_estop_active())

        # 2. Obstacle disappears (pin returns to HIGH / 1)
        self.sm._simulate_gpio_level(1)

        status = self.sm.get_status()
        self.assertFalse(status.ir_obstacle_detected)
        # CRITICAL REQUIREMENT: E-stop must REMAIN latched even after obstacle disappears
        self.assertTrue(status.obstacle_estop_active)
        self.assertTrue(status.obstacle_estop_latched)
        self.assertEqual(status.obstacle_estop_reason, "IR_OBSTACLE_DETECTED")
        # Reset is now allowed because path is physically clear
        self.assertTrue(status.reset_allowed)

    def test_reset_rejection_while_obstacle_detected(self):
        self.sm.register_get_operating_mode_callback(lambda: "semi_autonomous")

        # Trigger obstacle
        self.sm._simulate_gpio_level(0)

        # Attempt reset while obstacle is STILL in path
        with self.assertRaises(ValueError):
            self.sm.reset_estop()

        # E-stop must remain active
        self.assertTrue(self.sm.is_estop_active())

    def test_reset_success_when_clear(self):
        self.sm.register_get_operating_mode_callback(lambda: "semi_autonomous")

        # 1. Trigger obstacle
        self.sm._simulate_gpio_level(0)
        self.assertTrue(self.sm.is_estop_active())

        # 2. Clear obstacle
        self.sm._simulate_gpio_level(1)
        self.assertFalse(self.sm.is_obstacle_detected())

        # 3. Explicit operator reset
        res = self.sm.reset_estop()
        self.assertEqual(res["status"], "ok")

        status = self.sm.get_status()
        self.assertFalse(status.obstacle_estop_active)
        self.assertFalse(status.obstacle_estop_latched)
        self.assertIsNone(status.obstacle_estop_reason)

    def test_reset_rejection_when_sensor_disconnected(self):
        self.sm._obstacle_estop_active = True
        self.sm._obstacle_estop_latched = True
        self.sm._ir_sensor_connected = False

        with self.assertRaises(ValueError):
            self.sm.reset_estop()


if __name__ == "__main__":
    unittest.main()
