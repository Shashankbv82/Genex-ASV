"""
GENEX ASV - RC Signal Processing
Adapted from proven reference implementation in ASV_Backend.
Handles Channel Normalization, Inversion, Zero-Check, Deadband, and Expo.
"""

from typing import Optional
from backend.config import settings


class SignalProcessor:
    """Fast, deterministic signal processor for FlySky RC stick inputs."""

    def __init__(
        self,
        throttle_min_us: int = settings.RC_THROTTLE_MIN_US,
        throttle_max_us: int = settings.RC_THROTTLE_MAX_US,
        throttle_deadband_us: float = settings.RC_THROTTLE_DEADBAND_US,
        steering_min_us: int = settings.RC_STEERING_MIN_US,
        steering_neutral_us: int = settings.RC_STEERING_NEUTRAL_US,
        steering_max_us: int = settings.RC_STEERING_MAX_US,
        steering_deadband_us: float = settings.RC_STEERING_DEADBAND_US,
        min_us: int = settings.RC_MIN_US,
        neutral_us: int = settings.RC_NEUTRAL_US,
        max_us: int = settings.RC_MAX_US,
        deadband_us: float = settings.RC_DEADBAND_US,
        expo_factor: float = settings.RC_EXPO_FACTOR,
        zero_tolerance_us: float = settings.RC_THROTTLE_ZERO_TOLERANCE_US,
    ) -> None:
        self.throttle_min_us = throttle_min_us
        self.throttle_max_us = throttle_max_us
        self.throttle_deadband_us = throttle_deadband_us
        self.steering_min_us = steering_min_us
        self.steering_neutral_us = steering_neutral_us
        self.steering_max_us = steering_max_us
        self.steering_deadband_us = steering_deadband_us
        self.min_us = min_us
        self.neutral_us = neutral_us
        self.max_us = max_us
        self.deadband_us = deadband_us
        self.expo = expo_factor
        self.zero_tolerance_us = zero_tolerance_us

    def is_throttle_at_zero(self, raw_us: Optional[int]) -> bool:
        """
        Check if throttle stick is resting safely at Zero / Idle.
        For calibrated forward-only throttle, idle is <= throttle_min_us + zero_tolerance_us.
        Returns False if raw_us is None (unavailable / disconnected).
        """
        if raw_us is None:
            return False
        threshold = self.throttle_min_us + max(self.throttle_deadband_us, self.zero_tolerance_us)
        return raw_us <= threshold

    def process_steering(self, raw_us: Optional[int]) -> float:
        """
        Processes raw microsecond steering pulse into normalized [-1.0, +1.0] value.
        - full left (1050 us) -> -1.0
        - center (1500 us) -> 0.0
        - full right (2025 us) -> +1.0
        Applies a center deadband around 1500 us to prevent small RC noise from creating differential thrust.
        Returns 0.0 (center) if raw_us is None.
        """
        if raw_us is None:
            return 0.0
        clamped = max(self.steering_min_us, min(self.steering_max_us, raw_us))
        offset = clamped - self.steering_neutral_us

        if abs(offset) <= self.steering_deadband_us:
            return 0.0

        if offset < 0:
            usable_range = (self.steering_neutral_us - self.steering_deadband_us) - self.steering_min_us
            val = (offset + self.steering_deadband_us) / usable_range if usable_range > 0 else -1.0
        else:
            usable_range = self.steering_max_us - (self.steering_neutral_us + self.steering_deadband_us)
            val = (offset - self.steering_deadband_us) / usable_range if usable_range > 0 else 1.0

        return round(max(-1.0, min(1.0, val)), 4)

    def process_throttle(self, raw_us: Optional[int]) -> float:
        """
        Processes raw microsecond throttle pulse into normalized [0.0, 1.0] forward thrust.
        Calibrated linear throttle mapping: T = clamp((raw_throttle_us - 1010) / (2000 - 1010), 0.0, 1.0)
        Maintains a small zero deadband around measured minimum (1010–1025 us) so transmitter
        noise does not create propulsion. Maximum usable low-throttle resolution.
        Returns 0.0 if raw_us is None.
        """
        if raw_us is None:
            return 0.0

        if raw_us <= (self.throttle_min_us + self.throttle_deadband_us):
            return 0.0

        span = float(self.throttle_max_us - self.throttle_min_us)
        norm = (raw_us - self.throttle_min_us) / span if span > 0 else 0.0
        return round(max(0.0, min(1.0, norm)), 4)

    def is_manual_requested(self, raw_arm_us: Optional[int]) -> bool:
        """
        Evaluates CH5 SWD switch state.
        Returns True only if raw_arm_us is valid and in the configured Manual Mode position.
        Returns False if raw_arm_us is None (unavailable / disconnected).
        """
        if raw_arm_us is None:
            return False
        if settings.RC_ARM_WHEN_HIGH:
            return raw_arm_us >= settings.RC_ARM_THRESHOLD_US
        else:
            return raw_arm_us < settings.RC_ARM_THRESHOLD_US
