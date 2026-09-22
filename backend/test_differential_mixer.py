"""
GENEX ASV - Unit Tests for Differential Drive Mixer and Motor Controller
Verifies skid-steer mixing, saturation scaling, rate-limiter,
zero-throttle startup safety interlock, and emergency neutral stops.
"""

import unittest
from backend.control.mixer import DifferentialDriveMixer
from backend.control.motor_driver import PureLinearRateLimiter, MotorController
from backend.config import settings


class TestDifferentialDriveMixer(unittest.TestCase):
    def setUp(self):
        # Explicitly use +1.0 inverts for predictable test baseline
        self.mixer = DifferentialDriveMixer(left_invert=1.0, right_invert=1.0)

    def test_neutral_mixing(self):
        left, right = self.mixer.mix(0.0, 0.0)
        self.assertEqual(left, 0.0)
        self.assertEqual(right, 0.0)

    def test_straight_forward(self):
        left, right = self.mixer.mix(0.5, 0.0)
        self.assertEqual(left, 0.5)
        self.assertEqual(right, 0.5)

        left, right = self.mixer.mix(1.0, 0.0)
        self.assertEqual(left, 1.0)
        self.assertEqual(right, 1.0)

    def test_zero_throttle_invariant(self):
        """At zero throttle, steering MUST NOT create propulsion (must output 0.0, 0.0)."""
        # Full right steering (+1.0), zero throttle
        left, right = self.mixer.mix(0.0, 1.0)
        self.assertEqual(left, 0.0)
        self.assertEqual(right, 0.0)

        # Full left steering (-1.0), zero throttle
        left, right = self.mixer.mix(0.0, -1.0)
        self.assertEqual(left, 0.0)
        self.assertEqual(right, 0.0)

        # Partial steering, zero throttle
        left, right = self.mixer.mix(0.0, 0.5)
        self.assertEqual(left, 0.0)
        self.assertEqual(right, 0.0)

    def test_differential_forward_thrust(self):
        """Verify coupled differential thrust calculations matching new control law."""
        # T=0.20, S=+0.30 -> LEFT=0.26, RIGHT=0.14
        left, right = self.mixer.mix(0.20, 0.30)
        self.assertEqual(left, 0.26)
        self.assertEqual(right, 0.14)

        # T=0.20, S=-0.30 -> LEFT=0.14, RIGHT=0.26
        left, right = self.mixer.mix(0.20, -0.30)
        self.assertEqual(left, 0.14)
        self.assertEqual(right, 0.26)

        # T=0.50, S=+0.30 -> LEFT=0.65, RIGHT=0.35
        left, right = self.mixer.mix(0.50, 0.30)
        self.assertEqual(left, 0.65)
        self.assertEqual(right, 0.35)

        # T=0.50, S=-0.30 -> LEFT=0.35, RIGHT=0.65
        left, right = self.mixer.mix(0.50, -0.30)
        self.assertEqual(left, 0.35)
        self.assertEqual(right, 0.65)

        # T=1.00, S=+0.30 -> LEFT=1.00 (clamped), RIGHT=0.70
        left, right = self.mixer.mix(1.00, 0.30)
        self.assertEqual(left, 1.0)
        self.assertEqual(right, 0.70)


class TestPureLinearRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = PureLinearRateLimiter(accel_rate=1.0, decel_rate=2.0)

    def test_acceleration_ramp(self):
        val = self.limiter.update(target=1.0, dt=0.2)
        self.assertAlmostEqual(val, 0.2, places=3)
        val = self.limiter.update(target=1.0, dt=0.3)
        self.assertAlmostEqual(val, 0.5, places=3)

    def test_deceleration_ramp(self):
        self.limiter.snap_to(1.0)
        val = self.limiter.update(target=0.0, dt=0.2)
        # decel_rate=2.0 -> 1.0 - (2.0 * 0.2) = 0.6
        self.assertAlmostEqual(val, 0.6, places=3)

    def test_snap_to_neutral(self):
        self.limiter.snap_to(0.8)
        self.limiter.snap_to(0.0)
        self.assertEqual(self.limiter.current_val, 0.0)


class TestMotorController(unittest.TestCase):
    def setUp(self):
        self.mc = MotorController(
            throttle_accel_rate=2.0,
            throttle_decel_rate=4.0,
            steering_accel_rate=3.0,
            steering_decel_rate=6.0,
            motors_enabled=False,
        )

    def test_zero_throttle_startup_safety_interlock(self):
        """Arming must be blocked if throttle is non-zero when CH5 is flipped ON."""
        # 1. Arm switch flipped ON, but throttle stick is elevated
        armed = self.mc.update_arming_state(ch5_active=True, is_throttle_zero=False)
        self.assertFalse(armed)
        self.assertFalse(self.mc.is_armed)

        # Output remains neutral
        l_out, r_out, l_pwm, r_pwm, *_ = self.mc.process_and_output(raw_thr=0.5, raw_str=0.0, dt=0.02)
        self.assertEqual(l_out, 0.0)
        self.assertEqual(r_out, 0.0)
        self.assertEqual(l_pwm, settings.PWM_NEUTRAL_US)
        self.assertEqual(r_pwm, settings.PWM_NEUTRAL_US)

        # 2. Throttle stick moved to zero
        armed = self.mc.update_arming_state(ch5_active=True, is_throttle_zero=True)
        self.assertTrue(armed)
        self.assertTrue(self.mc.is_armed)

        # 3. Now throttle input generates motor output
        l_out, r_out, l_pwm, r_pwm, *_ = self.mc.process_and_output(raw_thr=0.5, raw_str=0.0, dt=0.5)
        self.assertGreater(l_out, 0.0)
        self.assertGreater(r_out, 0.0)
        self.assertGreater(l_pwm, settings.PWM_NEUTRAL_US)

    def test_immediate_neutral_stop(self):
        """Emergency stop must immediately reset outputs to neutral and require zero throttle again."""
        self.mc.update_arming_state(ch5_active=True, is_throttle_zero=True)
        self.mc.process_and_output(raw_thr=0.8, raw_str=0.0, dt=0.5)

        self.mc.immediate_neutral_stop()
        self.assertFalse(self.mc.is_armed)
        self.assertTrue(self.mc.require_throttle_zero)
        self.assertEqual(self.mc.left_output, 0.0)
        self.assertEqual(self.mc.right_output, 0.0)
        self.assertEqual(self.mc.left_pwm_us, settings.PWM_NEUTRAL_US)
        self.assertEqual(self.mc.right_pwm_us, settings.PWM_NEUTRAL_US)
        self.assertEqual(self.mc.actual_throttle, 0.0)
        self.assertEqual(self.mc.actual_steering, 0.0)

    def test_safe_bench_test_mode(self):
        """Motors enabled flag must be False during bench testing."""
        self.assertFalse(self.mc.motors_enabled)


if __name__ == "__main__":
    unittest.main()
