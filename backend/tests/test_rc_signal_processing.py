"""
GENEX ASV - Unit Tests for RC Signal Processing
Verifies deadband subtraction, piecewise forward throttle curve, steering expo,
and channel state helper functions.
"""

import unittest
from backend.rc.signal_processing import SignalProcessor
from backend.config import settings


class TestRCSignalProcessing(unittest.TestCase):
    def setUp(self):
        self.processor = SignalProcessor()

    def test_steering_center_deadband(self):
        """Steering pulses within the deadband around 1500 us must return exactly 0.0."""
        self.assertEqual(self.processor.process_steering(1500), 0.0)
        self.assertEqual(self.processor.process_steering(1520), 0.0)
        self.assertEqual(self.processor.process_steering(1480), 0.0)
        self.assertEqual(self.processor.process_steering(1500 + int(settings.RC_STEERING_DEADBAND_US) - 1), 0.0)
        self.assertEqual(self.processor.process_steering(1500 - int(settings.RC_STEERING_DEADBAND_US) + 1), 0.0)

    def test_steering_endpoints(self):
        """Full left (1050 us) should map to -1.0, full right (2025 us) to +1.0."""
        self.assertAlmostEqual(self.processor.process_steering(1050), -1.0, places=3)
        self.assertAlmostEqual(self.processor.process_steering(2025), 1.0, places=3)

    def test_steering_clamping(self):
        """Out of range values must be clamped to [-1.0, 1.0]."""
        self.assertAlmostEqual(self.processor.process_steering(800), -1.0, places=3)
        self.assertAlmostEqual(self.processor.process_steering(2200), 1.0, places=3)

    def test_throttle_idle_deadband(self):
        """Throttle pulses below deadband threshold (<= 1025 us) must return 0.0."""
        self.assertEqual(self.processor.process_throttle(1000), 0.0)
        self.assertEqual(self.processor.process_throttle(1010), 0.0)
        self.assertEqual(self.processor.process_throttle(1015), 0.0)
        self.assertEqual(self.processor.process_throttle(1025), 0.0)

    def test_throttle_endpoints(self):
        """Full throttle (2000 us) should map to 1.0."""
        self.assertAlmostEqual(self.processor.process_throttle(2000), 1.0, places=3)
        self.assertAlmostEqual(self.processor.process_throttle(2100), 1.0, places=3)

    def test_throttle_calibrated_linear_mapping(self):
        """Calibrated linear mapping provides maximum usable low-speed resolution."""
        t_low = self.processor.process_throttle(1144)
        self.assertAlmostEqual(t_low, round((1144 - 1010) / 990.0, 4), places=3)
        t_mid = self.processor.process_throttle(1570)
        self.assertAlmostEqual(t_mid, round((1570 - 1010) / 990.0, 4), places=3)

    def test_is_throttle_at_zero(self):
        """Test zero-throttle detection helper with calibrated bounds."""
        self.assertTrue(self.processor.is_throttle_at_zero(1000))
        self.assertTrue(self.processor.is_throttle_at_zero(1010))
        self.assertTrue(self.processor.is_throttle_at_zero(1015))
        self.assertTrue(self.processor.is_throttle_at_zero(1025))
        self.assertFalse(self.processor.is_throttle_at_zero(1100))
        self.assertFalse(self.processor.is_throttle_at_zero(1500))

    def test_is_manual_requested(self):
        """Test CH5 arming switch detection."""
        self.assertFalse(self.processor.is_manual_requested(1000))
        self.assertFalse(self.processor.is_manual_requested(1499))
        self.assertTrue(self.processor.is_manual_requested(1500))
        self.assertTrue(self.processor.is_manual_requested(2000))

    def test_none_channels_safety(self):
        """None channel inputs (disconnected / unavailable) must return fail-safe values."""
        self.assertFalse(self.processor.is_throttle_at_zero(None))
        self.assertFalse(self.processor.is_manual_requested(None))
        self.assertEqual(self.processor.process_steering(None), 0.0)
        self.assertEqual(self.processor.process_throttle(None), 0.0)


if __name__ == "__main__":
    unittest.main()
