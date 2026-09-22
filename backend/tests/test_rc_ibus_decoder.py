"""
GENEX ASV - Unit Tests for FlySky iBUS Protocol Decoder
Verifies frame scanning, 16-bit summation checksum, channel unpacking,
GPIO edge stream deserialization, and failsafe timeout detection.
"""

import time
import unittest
from unittest.mock import MagicMock
from backend.rc.ibus_decoder import IBusDecoder


def build_ibus_frame(channel_values: list[int]) -> bytes:
    """Helper to construct a valid 32-byte iBUS frame."""
    assert len(channel_values) == 14
    header = bytes([0x20, 0x40])
    ch_bytes = bytearray()
    for val in channel_values:
        ch_bytes.extend(int(val).to_bytes(2, "little"))
    payload = header + bytes(ch_bytes)
    chk = 0xFFFF - sum(payload)
    return payload + chk.to_bytes(2, "little")


class TestIBusDecoder(unittest.TestCase):
    def setUp(self):
        self.decoder = IBusDecoder(port="dummy", baudrate=115200, failsafe_timeout=0.20)

    def test_checksum_verification(self):
        """Test checksum calculation and validation."""
        channels = [1500] * 14
        channels[2] = 1000  # CH3 throttle
        valid_frame = build_ibus_frame(channels)
        self.assertEqual(len(valid_frame), 32)
        self.assertTrue(self.decoder._verify_checksum(valid_frame))

        # Corrupt one byte
        corrupt = bytearray(valid_frame)
        corrupt[10] ^= 0xFF
        self.assertFalse(self.decoder._verify_checksum(bytes(corrupt)))

    def test_unpack_frame(self):
        """Test channel extraction from valid frame."""
        channels = [1000 + (i * 50) for i in range(14)]
        frame = build_ibus_frame(channels)
        self.decoder._unpack_frame(frame)

        for i in range(14):
            self.assertEqual(self.decoder.channels[i + 1], channels[i])

    def test_invalid_channel_clamping(self):
        """Out of range channels (<800 or >2200) should be rejected during unpack."""
        channels = [1500] * 14
        channels[0] = 500   # Below minimum
        channels[1] = 2500  # Above maximum
        frame = build_ibus_frame(channels)
        self.decoder.channels[1] = 1500
        self.decoder.channels[2] = 1500
        self.decoder._unpack_frame(frame)
        # Invalid values must not overwrite previous valid channel values
        self.assertEqual(self.decoder.channels[1], 1500)
        self.assertEqual(self.decoder.channels[2], 1500)

    def test_read_channels_with_mock_serial(self):
        """Test streaming parsing with mock serial."""
        mock_ser = MagicMock()
        mock_ser.is_open = True
        self.decoder.ser = mock_ser

        channels = [1500] * 14
        channels[0] = 1200  # Steering
        channels[2] = 1400  # Throttle
        channels[4] = 2000  # CH5 Armed
        frame = build_ibus_frame(channels)

        # Prepend some garbage bytes before the frame
        mock_ser.in_waiting = len(frame) + 5
        mock_ser.read.return_value = b"\x00\xFF\x12\x34\x56" + frame

        ch, age, healthy = self.decoder.read_channels()
        self.assertTrue(healthy)
        self.assertLess(age, 0.1)
        self.assertEqual(ch[1], 1200)
        self.assertEqual(ch[3], 1400)
        self.assertEqual(ch[5], 2000)
        self.assertEqual(self.decoder.valid_frames, 1)

    def test_initial_state_unavailable_channels(self):
        """Before any valid frame arrives, read_channels must return None channels and False."""
        ch, age, healthy = self.decoder.read_channels()
        self.assertFalse(healthy)
        self.assertEqual(age, 999.0)
        self.assertIsNone(ch[1])
        self.assertIsNone(ch[3])
        self.assertIsNone(ch[5])

    def test_failsafe_timeout(self):
        """When no new frames arrive beyond failsafe_timeout, is_healthy must be False and channels None."""
        self.decoder.last_frame_time = time.monotonic() - 0.50  # 500ms ago
        mock_ser = MagicMock()
        mock_ser.is_open = True
        mock_ser.in_waiting = 0
        mock_ser.read.return_value = b""
        self.decoder.ser = mock_ser

        ch, age, healthy = self.decoder.read_channels()
        self.assertFalse(healthy)
        self.assertGreater(age, 0.20)
        self.assertIsNone(ch[1])
        self.assertIsNone(ch[3])
        self.assertIsNone(ch[5])

    def test_feed_bytes_helper(self):
        """Test direct frame feeding via feed_bytes_for_testing."""
        channels = [1500] * 14
        channels[0] = 1600
        frame = build_ibus_frame(channels)

        self.assertTrue(self.decoder.feed_bytes_for_testing(frame))
        self.assertEqual(self.decoder.valid_frames, 1)
        self.assertEqual(self.decoder.channels[1], 1600)

        # Feeding invalid checksum should return False and increment checksum_errors
        corrupt = bytearray(frame)
        corrupt[30] ^= 0x55
        self.assertFalse(self.decoder.feed_bytes_for_testing(bytes(corrupt)))
        self.assertEqual(self.decoder.checksum_errors, 1)

    def test_gpio_edge_deserialization(self):
        """Test deserialization of simulated edge timestamps into a verified 32-byte iBUS frame."""
        channels = [1500] * 14
        channels[0] = 1510  # Steering
        channels[2] = 1005  # Throttle zero
        channels[4] = 1000  # Disarmed
        frame = build_ibus_frame(channels)

        # Synthesize 115200 baud 8N1 edge timestamps for the 32 bytes
        bit_ns = int(1_000_000_000.0 / 115200.0)  # ~8680 ns
        t_cur = 100_000_000  # Arbitrary base timestamp
        edges = []

        cur_lvl = 1  # Idle high
        for byte_val in frame:
            # Start bit (0)
            if cur_lvl != 0:
                edges.append((t_cur, 0))
                cur_lvl = 0
            t_cur += bit_ns

            # 8 data bits
            for bit in range(8):
                bit_lvl = (byte_val >> bit) & 1
                if bit_lvl != cur_lvl:
                    edges.append((t_cur, bit_lvl))
                    cur_lvl = bit_lvl
                t_cur += bit_ns

            # Stop bit (1)
            if cur_lvl != 1:
                edges.append((t_cur, 1))
                cur_lvl = 1
            t_cur += bit_ns
            # Fractional inter-byte idle
            t_cur += int(0.2 * bit_ns)

        # Add closing edge
        edges.append((t_cur, 1))

        # Feed to decoder's edge processor
        gpio_decoder = IBusDecoder(pin=22, failsafe_timeout=0.20)
        gpio_decoder._process_frame_edges(edges)

        self.assertEqual(gpio_decoder.valid_frames, 1)
        ch, age, healthy = gpio_decoder.read_channels()
        self.assertTrue(healthy)
        self.assertEqual(ch[1], 1510)
        self.assertEqual(ch[3], 1005)
        self.assertEqual(ch[5], 1000)


if __name__ == "__main__":
    unittest.main()
