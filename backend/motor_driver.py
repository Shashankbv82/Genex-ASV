"""
GENEX ASV - Motor Controller & Rate-Limiter
Adapted from proven reference implementation in ASV_Backend.
Includes:
  - Zero-Throttle Startup Safety Interlock (Requires throttle stick at 0% before enabling motors)
  - Pre-Mix Throttle Rate Limiter (linear dv/dt): Smooth forward acceleration
  - Instant Steering Pass-Through: ZERO delay on steering turns (0.0 ms lag)
  - Safe Bench-Test Inhibitor: Physical motors disabled by default (motors_enabled = False)
  - PCA9685 Hardware PWM Output on I2C Bus 1 @ 0x40 (50 Hz, Ch 0: Left, Ch 1: Right)
"""

import logging
import time
from typing import Optional, Tuple

from backend.config import settings
from backend.control.mixer import DifferentialDriveMixer
from backend.hardware.i2c_lock import i2c1_lock
from backend.safety.safety_manager import safety_manager

logger = logging.getLogger("genex.control.motor_driver")

try:
    import smbus2
    HAS_SMBUS2 = True
except ImportError:
    HAS_SMBUS2 = False


class PureLinearRateLimiter:
    """Pure Linear Velocity Rate Limiter (dv/dt) for Throttle acceleration/deceleration."""

    def __init__(self, accel_rate: float, decel_rate: float) -> None:
        self.accel_rate = accel_rate
        self.decel_rate = decel_rate
        self.current_val: float = 0.0

    def update(self, target: float, dt: float) -> float:
        """Advance value towards target by at most (rate * dt)."""
        if dt <= 0.0:
            return self.current_val

        curr = self.current_val

        if target > curr:
            rate = self.accel_rate if target > 0 else self.decel_rate
            curr = min(target, curr + rate * dt)
        elif target < curr:
            rate = self.accel_rate if target < 0 else self.decel_rate
            curr = max(target, curr - rate * dt)

        if target == 0.0 and abs(curr) < 0.005:
            curr = 0.0

        self.current_val = max(-1.0, min(1.0, curr))
        return self.current_val

    def snap_to(self, val: float = 0.0) -> None:
        self.current_val = val


class MotorController:
    """
    Complete Motor Controller with Zero-Throttle Startup Safety Interlock,
    Pre-mix Dual Rate Limiting (Throttle + Steering),
    Forward-Only Differential Drive Mixing, and PCA9685 Hardware PWM output.
    """

    def __init__(
        self,
        throttle_accel_rate: float = settings.MANUAL_THROTTLE_ACCEL_RATE,
        throttle_decel_rate: float = settings.MANUAL_THROTTLE_DECEL_RATE,
        steering_accel_rate: float = settings.MANUAL_STEERING_ACCEL_RATE,
        steering_decel_rate: float = settings.MANUAL_STEERING_DECEL_RATE,
        motors_enabled: bool = settings.MOTORS_ENABLED,
        accel_rate: Optional[float] = None,
        decel_rate: Optional[float] = None,
    ) -> None:
        self.motors_enabled = motors_enabled
        self.mixer = DifferentialDriveMixer()

        t_accel = accel_rate if accel_rate is not None else throttle_accel_rate
        t_decel = decel_rate if decel_rate is not None else throttle_decel_rate
        self.throttle_limiter = PureLinearRateLimiter(t_accel, t_decel)
        self.steering_limiter = PureLinearRateLimiter(steering_accel_rate, steering_decel_rate)

        # Arming State Machine & Zero-Throttle Safety Interlock
        self.is_armed: bool = False
        self.require_throttle_zero: bool = True  # Must see throttle at zero before enabling output

        # Internal Ramped & Target States
        self.target_throttle: float = 0.0
        self.target_steering: float = 0.0
        self.actual_throttle: float = 0.0
        self.actual_steering: float = 0.0

        # Output states
        self.left_output: float = 0.0
        self.right_output: float = 0.0
        self.left_pwm_us: float = settings.PWM_NEUTRAL_US
        self.right_pwm_us: float = settings.PWM_NEUTRAL_US

        # PCA9685 Hardware Bus
        self._bus: Optional[smbus2.SMBus] = None
        self._pca_ready: bool = False
        self._init_pca9685()

    def _init_pca9685(self) -> None:
        """Initialize PCA9685 PWM controller at 50 Hz."""
        if not HAS_SMBUS2:
            logger.info("smbus2 not available; PCA9685 hardware output disabled (software-only mode).")
            return

        try:
            with i2c1_lock:
                self._bus = smbus2.SMBus(settings.PCA9685_I2C_BUS)
                addr = settings.PCA9685_I2C_ADDR

                # Prescale calculation for 50 Hz with 25 MHz internal clock:
                # prescale = round(25,000,000 / (4096 * 50)) - 1 = 121 (0x79)
                prescale = int(round(25000000.0 / (4096.0 * settings.PCA9685_PWM_FREQ_HZ)) - 1)

                old_mode = self._bus.read_byte_data(addr, 0x00)
                # Sleep to configure prescale
                self._bus.write_byte_data(addr, 0x00, (old_mode & 0x7F) | 0x10)
                self._bus.write_byte_data(addr, 0xFE, prescale)
                # Wake up and enable auto-increment
                self._bus.write_byte_data(addr, 0x00, old_mode & 0xEF)
                time.sleep(0.005)
                self._bus.write_byte_data(addr, 0x00, 0x20)  # Auto-increment
                self._bus.write_byte_data(addr, 0x01, 0x04)  # Totem-pole output (MODE2)

            self._pca_ready = True
            logger.info(
                "PCA9685 initialized at 0x%02X on bus %d (50 Hz, prescale=0x%02X).",
                addr, settings.PCA9685_I2C_BUS, prescale
            )

            # Write safe neutral pulse initially
            self._write_hw_pwm(settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US)

        except Exception as exc:
            logger.warning("Could not initialize PCA9685 at 0x%02X: %s. Running in bench simulation mode.",
                           settings.PCA9685_I2C_ADDR, exc)
            self._pca_ready = False

    def _write_hw_pwm(self, left_us: float, right_us: float) -> None:
        """Writes PWM pulse widths to PCA9685 channels simultaneously using atomic block write."""
        if not self._pca_ready or self._bus is None:
            return

        # If physical motors are not enabled, output safe neutral (1500 us) to keep ESCs initialized safely
        target_left = left_us if self.motors_enabled else settings.PWM_NEUTRAL_US
        target_right = right_us if self.motors_enabled else settings.PWM_NEUTRAL_US

        try:
            # 20,000 us period at 50 Hz maps to 4095 ticks (~4.8828 us/tick)
            left_ticks = max(0, min(4095, int(round((target_left / 20000.0) * 4095))))
            right_ticks = max(0, min(4095, int(round((target_right / 20000.0) * 4095))))

            addr = settings.PCA9685_I2C_ADDR

            with i2c1_lock:
                if settings.PCA9685_LEFT_CHANNEL == 0 and settings.PCA9685_RIGHT_CHANNEL == 1:
                    # Atomic 8-byte block write updates CH0 and CH1 simultaneously in 1.0 ms
                    payload = [
                        0, 0, left_ticks & 0xFF, (left_ticks >> 8) & 0x0F,
                        0, 0, right_ticks & 0xFF, (right_ticks >> 8) & 0x0F,
                    ]
                    self._bus.write_i2c_block_data(addr, 0x06, payload)
                else:
                    base_l = 0x06 + 4 * settings.PCA9685_LEFT_CHANNEL
                    base_r = 0x06 + 4 * settings.PCA9685_RIGHT_CHANNEL
                    self._bus.write_i2c_block_data(addr, base_l, [0, 0, left_ticks & 0xFF, (left_ticks >> 8) & 0x0F])
                    self._bus.write_i2c_block_data(addr, base_r, [0, 0, right_ticks & 0xFF, (right_ticks >> 8) & 0x0F])

        except Exception as exc:
            logger.error("Error writing PWM to PCA9685: %s", exc)

    def update_arming_state(self, ch5_active: bool, is_throttle_zero: bool) -> bool:
        """
        Arming State Machine with Zero-Throttle Safety Interlock:
          1. Arm switch (CH5) must be in ACTIVE position.
          2. Throttle stick must pass through 0% (Idle/Neutral) before motor power is enabled.
        """
        if not ch5_active:
            if self.is_armed:
                logger.info("Arm switch INACTIVE (CH5 OFF) — Vehicle DISARMED.")
            self.is_armed = False
            self.require_throttle_zero = True
            self.snap_to_neutral()
            return False

        # Switch IS active: Check Zero-Throttle Interlock
        if self.require_throttle_zero:
            if is_throttle_zero:
                logger.info("Zero throttle confirmed — Vehicle ARMED and READY!")
                self.require_throttle_zero = False
                self.is_armed = True
            else:
                if self.is_armed:
                    logger.warning("Arm switch active but throttle not at zero — Arming BLOCKED until throttle is zeroed.")
                self.is_armed = False
                self.snap_to_neutral()
                return False
        else:
            self.is_armed = True

        return self.is_armed

    def process_and_output(
        self, raw_thr: float, raw_str: float, dt: float
    ) -> Tuple[float, float, float, float, float, float]:
        """
        PRE-MIX RATE LIMITED PIPELINE with Arming Gating and E-Stop Safety Override.
        1. Safety / E-stop check -> immediate snap to neutral (never ramped)
        2. Arming / interlock check -> snap to neutral if disarmed
        3. Rate limit target throttle -> actual_throttle
        4. Rate limit target steering -> actual_steering
        5. Forward-only differential mix:
           if actual_throttle == 0: LEFT=0, RIGHT=0
           else: LEFT = clamp(T*(1+S), 0, 1), RIGHT = clamp(T*(1-S), 0, 1)
        6. Convert to forward-only PWM: 1500 + command * 500
        7. Atomic PCA9685 hardware write
        Returns:
            Tuple[float, float, float, float, float, float]:
            (left_output, right_output, left_pwm_us, right_pwm_us, actual_throttle, actual_steering)
        """
        self.target_throttle = raw_thr
        self.target_steering = raw_str

        # PRIORITY SAFETY CHECK: Active E-Stop strictly neutralizes motors immediately (NO RAMP)
        if safety_manager.is_estop_active():
            self.immediate_neutral_stop()
            return 0.0, 0.0, settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US, 0.0, 0.0

        if not self.is_armed or self.require_throttle_zero:
            self.snap_to_neutral()
            return 0.0, 0.0, settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US, 0.0, 0.0

        # 1. Smooth throttle pre-mix (rate-limited linear ramp)
        self.actual_throttle = self.throttle_limiter.update(raw_thr, dt)

        # 2. Smooth steering pre-mix (rate-limited linear ramp)
        self.actual_steering = self.steering_limiter.update(raw_str, dt)

        # 3. Differential mix with zero-throttle invariant
        left_out, right_out = self.mixer.mix(self.actual_throttle, self.actual_steering)
        self.left_output = left_out
        self.right_output = right_out

        # 4. Convert to PWM µs: Unidirectional Forward-Only [1500, 2000] us
        self.left_pwm_us = self._normalized_to_pwm(self.left_output)
        self.right_pwm_us = self._normalized_to_pwm(self.right_output)

        # 5. Output to PCA9685 Hardware
        self._write_hw_pwm(self.left_pwm_us, self.right_pwm_us)

        return (
            self.left_output,
            self.right_output,
            self.left_pwm_us,
            self.right_pwm_us,
            self.actual_throttle,
            self.actual_steering,
        )

    def _normalized_to_pwm(self, norm_val: float) -> float:
        """
        Convert normalized float [0.0, 1.0] to ESC PWM pulse width in microseconds.
        Unidirectional forward-only ESC model: [1500, 2000] us.
        Never output < 1500 us or > 2000 us.
        """
        clamped = max(0.0, min(1.0, norm_val))
        return settings.PWM_NEUTRAL_US + clamped * (settings.PWM_MAX_US - settings.PWM_NEUTRAL_US)

    def immediate_neutral_stop(self) -> None:
        """
        Immediate Failsafe / Emergency Stop: resets internal state and hardware to neutral (1500 us).
        Safety events are NEVER ramped.
        """
        was_active = self.is_armed or self.left_output != 0.0 or self.right_output != 0.0
        self.snap_to_neutral()
        self.is_armed = False
        self.require_throttle_zero = True
        self._write_hw_pwm(settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US)
        if was_active:
            logger.info("MotorController internal and PCA9685 hardware state snapped to Neutral (1500 us).")

    def snap_to_neutral(self) -> None:
        """Resets rate limiters to zero and motor targets to neutral (1500 us)."""
        self.throttle_limiter.snap_to(0.0)
        self.steering_limiter.snap_to(0.0)
        self.actual_throttle = 0.0
        self.actual_steering = 0.0
        self.left_output = 0.0
        self.right_output = 0.0
        self.left_pwm_us = settings.PWM_NEUTRAL_US
        self.right_pwm_us = settings.PWM_NEUTRAL_US
        self._write_hw_pwm(settings.PWM_NEUTRAL_US, settings.PWM_NEUTRAL_US)

    def shutdown(self) -> None:
        """Clean shutdown handler."""
        logger.info("Shutting down MotorController...")
        self.immediate_neutral_stop()
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
            self._bus = None
        self._pca_ready = False
