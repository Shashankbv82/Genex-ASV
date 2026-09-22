"""
GENEX ASV - Skid-Steer / Differential Drive Mixer
Adapted from proven reference implementation in ASV_Backend.
Combines Throttle and Steering inputs into Left and Right motor targets.
"""

from typing import Tuple
from backend.config import settings


class DifferentialDriveMixer:
    """Forward-only differential drive mixer with zero-throttle invariant."""

    def __init__(self, left_invert: float = settings.LEFT_MOTOR_INVERT, right_invert: float = settings.RIGHT_MOTOR_INVERT) -> None:
        self.left_invert = left_invert
        self.right_invert = right_invert

    def mix(self, throttle: float, steering: float) -> Tuple[float, float]:
        """
        Mixes normalized actual throttle [0.0, 1.0] and actual steering [-1.0, +1.0]
        into forward-only left and right motor targets [0.0, 1.0].

        Zero-Throttle Invariant:
        If throttle <= 0.0, both left and right outputs are strictly 0.0 regardless of steering.

        Differential Thrust:
        LEFT  = clamp(T * (1.0 + S), 0.0, 1.0)
        RIGHT = clamp(T * (1.0 - S), 0.0, 1.0)
        """
        t = max(0.0, min(1.0, throttle))
        s = max(-1.0, min(1.0, steering))

        if t <= 0.0:
            return 0.0, 0.0

        left = t * (1.0 + s) * self.left_invert
        right = t * (1.0 - s) * self.right_invert

        left_clamped = max(0.0, min(1.0, left))
        right_clamped = max(0.0, min(1.0, right))

        return round(left_clamped, 4), round(right_clamped, 4)
