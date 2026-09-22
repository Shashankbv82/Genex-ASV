"""
GENEX ASV - FlySky PPM (Pulse Position Modulation) Hardware Decoder
Captures 50 Hz PPM frames on BCM GPIO 22 using lgpio kernel edge timestamping.

PPM Frame Timing:
  - Frame repetition: ~20 ms (50 Hz)
  - Channels 1..10  : Pulses between 800 µs and 2200 µs (1000 µs min, 1500 µs center, 2000 µs max)
  - Sync Gap        : > 3000 µs (typically 4000 µs - 12000 µs)
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("genex.rc.ppm_decoder")

try:
    import lgpio
    HAS_LGPIO = True
except ImportError:
    HAS_LGPIO = False


class PPMDecoder:
    """
    High-precision PPM decoder using Linux kernel edge event timestamps via lgpio.
    Operates on a dedicated GPIO pin without userspace bit-banging.
    """

    def __init__(
        self,
        pin: int = 22,
        chip: int = 0,
        failsafe_timeout: float = 0.20,
        sync_gap_us: float = 2700.0,
        min_channels: int = 4,
        max_channels: int = 14,
    ) -> None:
        self.pin = pin
        self.chip = chip
        self.failsafe_timeout = failsafe_timeout
        self.sync_gap_us = sync_gap_us
        self.min_channels = min_channels
        self.max_channels = max_channels

        self._lock = threading.Lock()
        self.channels: Dict[int, Optional[int]] = {ch: None for ch in range(1, 15)}
        self.last_frame_time: float = 0.0

        # Diagnostics
        self.total_frames: int = 0
        self.valid_frames: int = 0
        self.rejected_frames: int = 0
        self.glitch_count: int = 0

        # Edge state tracking
        self._last_edge_ns: int = 0
        self._current_pulses_us: List[int] = []
        self._handle: Optional[int] = None
        self._cb = None

    def open(self) -> bool:
        """Initialize GPIO pin and register kernel edge alert callback."""
        if not HAS_LGPIO:
            logger.warning("lgpio is not installed. PPM hardware decoding unavailable.")
            return False

        try:
            logger.info("Opening lgpio chip %d for PPM on BCM GPIO %d...", self.chip, self.pin)
            self._handle = lgpio.gpiochip_open(self.chip)
            res = lgpio.gpio_claim_alert(self._handle, self.pin, lgpio.RISING_EDGE)
            if res < 0:
                raise RuntimeError(f"lgpio.gpio_claim_alert failed on GPIO {self.pin} with code {res}")

            # Register callback on rising edge
            self._cb = lgpio.callback(
                self._handle,
                self.pin,
                lgpio.RISING_EDGE,
                self._edge_callback
            )
            logger.info("PPM decoder registered successfully on BCM GPIO %d with kernel alerts.", self.pin)
            return True
        except Exception as exc:
            logger.warning("Failed to initialize PPM on BCM GPIO %d: %s", self.pin, exc)
            self.close()
            return False

    def _edge_callback(self, chip: int, gpio: int, level: int, timestamp_ns: int) -> None:
        """
        Kernel edge interrupt handler.
        timestamp_ns is the kernel monotonic timestamp of the physical edge.
        """
        if self._last_edge_ns == 0:
            self._last_edge_ns = timestamp_ns
            return

        interval_us = (timestamp_ns - self._last_edge_ns) / 1000.0
        self._last_edge_ns = timestamp_ns

        # Glitch filter: ignore pulses shorter than 300 us
        if interval_us < 300.0:
            with self._lock:
                self.glitch_count += 1
                # If high frequency pulses (< 100 us) arrive in high volume, warn about i-BUS protocol mismatch
                if self.glitch_count == 100 or self.glitch_count % 20000 == 0:
                    logger.warning(
                        "High-frequency pulse train detected on GPIO %d (interval ~%.1f µs). "
                        "The receiver may be outputting 115200 baud i-BUS serial instead of PPM. "
                        "Verify receiver cable is plugged into 'CH 1 / PPM' (not 'SERVO/i-BUS') "
                        "and that PPM output is enabled on the transmitter.",
                        self.pin, interval_us
                    )
            return

        # Check for Sync Gap (> 3000 µs)
        if interval_us >= self.sync_gap_us:
            # Sync gap marks the end of the previous frame
            with self._lock:
                self.total_frames += 1
                if self.min_channels <= len(self._current_pulses_us) <= self.max_channels:
                    # Validate all channel pulses in the frame
                    all_valid = True
                    for pulse in self._current_pulses_us:
                        if not (800 <= pulse <= 2200):
                            all_valid = False
                            break

                    if all_valid:
                        for ch_idx, pulse_val in enumerate(self._current_pulses_us):
                            self.channels[ch_idx + 1] = int(pulse_val)
                        self.last_frame_time = time.monotonic()
                        self.valid_frames += 1
                        if self.valid_frames == 1 or self.valid_frames % 500 == 0:
                            logger.info(
                                "PPM frame lock: %d channels decoded (valid=%d, glitches=%d): %s",
                                len(self._current_pulses_us),
                                self.valid_frames,
                                self.glitch_count,
                                [self.channels[c] for c in range(1, len(self._current_pulses_us) + 1)]
                            )
                    else:
                        self.rejected_frames += 1
                        if self.rejected_frames == 1 or self.rejected_frames % 200 == 0:
                            logger.warning(
                                "PPM frame rejected (out of pulse range 800-2200): %s",
                                self._current_pulses_us
                            )
                elif len(self._current_pulses_us) > 0:
                    self.rejected_frames += 1
                    if self.rejected_frames == 1 or self.rejected_frames % 200 == 0:
                        logger.warning(
                            "PPM frame rejected (channel count %d outside [%d, %d]): %s",
                            len(self._current_pulses_us),
                            self.min_channels,
                            self.max_channels,
                            self._current_pulses_us
                        )

            self._current_pulses_us = []
        else:
            # Channel pulse
            if 800.0 <= interval_us <= 2200.0:
                self._current_pulses_us.append(int(interval_us))
            else:
                with self._lock:
                    self.glitch_count += 1

    def feed_pulse_for_testing(self, interval_us: float) -> None:
        """Synthetic test helper to feed pulse intervals directly."""
        now_ns = int(time.monotonic() * 1_000_000_000)
        self._edge_callback(self.chip, self.pin, 1, now_ns)

    def read_channels(self) -> Tuple[Dict[int, Optional[int]], float, bool]:
        """
        Returns thread-safe copy of latest decoded channels and health status.
        When link is unhealthy, disconnected, or stale, returns None for all channels.

        Returns:
            Tuple[Dict[int, Optional[int]], float, bool]: (channels, frame_age_sec, is_healthy)
        """
        now = time.monotonic()
        with self._lock:
            ch_copy = self.channels.copy()
            last_t = self.last_frame_time
            valid_cnt = self.valid_frames

        frame_age = now - last_t if last_t > 0.0 else 999.0
        is_healthy = (last_t > 0.0) and (valid_cnt > 0) and (frame_age <= self.failsafe_timeout)

        if not is_healthy:
            return {ch: None for ch in range(1, 15)}, frame_age, False

        return ch_copy, frame_age, True

    def close(self) -> None:
        """Clean shutdown handler."""
        if self._cb:
            try:
                self._cb.cancel()
            except Exception:
                pass
            self._cb = None

        if self._handle is not None and HAS_LGPIO:
            try:
                lgpio.gpio_free(self._handle, self.pin)
            except Exception:
                pass
            try:
                lgpio.gpiochip_close(self._handle)
                logger.info("PPM decoder on GPIO %d closed.", self.pin)
            except Exception as exc:
                logger.warning("Error closing lgpio handle: %s", exc)
            finally:
                self._handle = None
