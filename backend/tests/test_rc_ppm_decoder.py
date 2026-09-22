"""
GENEX ASV - Unit Tests for FlySky PPM Decoder
Verifies kernel edge timestamp processing, sync gap detection, glitch rejection,
channel pulse unpacking, and failsafe timeout detection.
"""

import time
import unittest
from backend.rc.ppm_decoder import PPMDecoder


class TestPPMDecoder(unittest.TestCase):
    def setUp(self):
        self.decoder = PPMDecoder(pin=22, failsafe_timeout=0.20, sync_gap_us=3000.0)

    def _feed_edge_sequence(self, pulse_intervals_us: list[float], sync_gap_us: float = 8000.0):
        """Helper to feed a simulated PPM frame of pulse intervals followed by a sync gap."""
        t_ns = 1_000_000_000  # Arbitrary base timestamp

        # Initial edge to establish baseline
        self.decoder._edge_callback(0, 22, 1, t_ns)

        # Pulse intervals
        for interval in pulse_intervals_us:
            t_ns += int(interval * 1000.0)
            self.decoder._edge_callback(0, 22, 1, t_ns)

        # Sync gap
        t_ns += int(sync_gap_us * 1000.0)
        self.decoder._edge_callback(0, 22, 1, t_ns)

    def test_valid_ppm_frame(self):
        """Test decoding of a valid 6-channel PPM frame."""
        pulses = [1500.0, 1500.0, 1000.0, 1500.0, 2000.0, 1500.0]
        self._feed_edge_sequence(pulses)

        ch, age, healthy = self.decoder.read_channels()
        self.assertTrue(healthy)
        self.assertLess(age, 0.1)
        self.assertEqual(ch[1], 1500)
        self.assertEqual(ch[2], 1500)
        self.assertEqual(ch[3], 1000)
        self.assertEqual(ch[4], 1500)
        self.assertEqual(ch[5], 2000)
        self.assertEqual(ch[6], 1500)
        self.assertEqual(self.decoder.valid_frames, 1)
        self.assertEqual(self.decoder.rejected_frames, 0)

    def test_glitch_rejection_short_pulse(self):
        """Pulses shorter than 300 us should be ignored as electrical glitches."""
        t_ns = 1_000_000_000
        self.decoder._edge_callback(0, 22, 1, t_ns)
        t_ns += int(100.0 * 1000.0)  # 100 us glitch
        self.decoder._edge_callback(0, 22, 1, t_ns)

        self.assertEqual(self.decoder.glitch_count, 1)

    def test_frame_with_too_few_channels_rejected(self):
        """Frames with fewer than min_channels (4) should be rejected."""
        pulses = [1500.0, 1200.0]  # Only 2 channels
        self._feed_edge_sequence(pulses)

        self.assertEqual(self.decoder.valid_frames, 0)
        self.assertEqual(self.decoder.rejected_frames, 1)

    def test_initial_state_unavailable_channels(self):
        """Before any frame is received, read_channels must return None channels and False."""
        ch, age, healthy = self.decoder.read_channels()
        self.assertFalse(healthy)
        self.assertEqual(age, 999.0)
        self.assertIsNone(ch[1])
        self.assertIsNone(ch[3])
        self.assertIsNone(ch[5])

    def test_failsafe_timeout(self):
        """If no new frame arrives for longer than failsafe_timeout, is_healthy must be False and channels None."""
        pulses = [1500.0, 1500.0, 1000.0, 1500.0]
        self._feed_edge_sequence(pulses)

        ch, age, healthy = self.decoder.read_channels()
        self.assertTrue(healthy)
        self.assertEqual(ch[1], 1500)

        # Simulate time passing
        self.decoder.last_frame_time = time.monotonic() - 0.25
        ch, age, healthy = self.decoder.read_channels()
        self.assertFalse(healthy)
        self.assertGreater(age, 0.20)
        self.assertIsNone(ch[1])
        self.assertIsNone(ch[3])
        self.assertIsNone(ch[5])


if __name__ == "__main__":
    unittest.main()
