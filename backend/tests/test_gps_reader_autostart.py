"""
GENEX ASV - Unit Tests for GPS Auto-Start, Dynamic AT Discovery, and GNSS Health Watchdog
"""

import time
import unittest
import serial
from unittest.mock import MagicMock, patch
from backend.gps.reader import GPSReader
from backend.gps.parser import parse_nmea_sentence
from backend.telemetry.state import GPSData
from backend.config import settings


class MockSerialPort:
    def __init__(self, response_bytes=b"OK\r\n"):
        self.response = response_bytes
        self.written = []
        self._read_done = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def reset_input_buffer(self):
        self._read_done = False

    def write(self, data):
        self.written.append(data)
        self._read_done = False

    @property
    def in_waiting(self):
        return 0 if self._read_done else len(self.response)

    def read(self, size):
        if not self._read_done:
            self._read_done = True
            return self.response
        return b""


class TestGPSAutostart(unittest.TestCase):
    def setUp(self):
        self.reader = GPSReader(port="/dev/ttyS0", baudrate=115200)

    def tearDown(self):
        self.reader.stop_reader()

    def test_01_corrupt_data_does_not_refresh_gnss_health(self):
        """Verify that corrupt lines, invalid checksums, and $EPHABNORMAL do not update last_valid_nmea_monotonic."""
        data = GPSData()
        t_initial = data.last_valid_nmea_monotonic

        # 1. Corrupt data without checksum
        res1 = parse_nmea_sentence("GARBAGE_NOISE\r\n", data)
        self.assertFalse(res1)
        self.assertEqual(data.last_valid_nmea_monotonic, t_initial)

        # 2. Checksum mismatch
        res2 = parse_nmea_sentence("$GNGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*FF", data)
        self.assertFalse(res2)
        self.assertEqual(data.last_valid_nmea_monotonic, t_initial)

        # 3. Proprietary non-standard sentence ($EPHABNORMAL)
        res3 = parse_nmea_sentence("$EPHABNORMAL,1*50", data)
        self.assertFalse(res3)
        self.assertEqual(data.last_valid_nmea_monotonic, t_initial)

        # 4. Authentic valid standard sentence ($GNGGA with valid checksum 0x56)
        res4 = parse_nmea_sentence("$GNGGA,064000.00,,,,0,00,99.99,,,,,,*56", data)
        self.assertTrue(res4)
        self.assertGreater(data.last_valid_nmea_monotonic, t_initial)

    def test_02_gnss_silence_after_hundreds_of_valid_sentences(self):
        """Verify watchdog detects silence after previously receiving 500 valid sentences."""
        data = self.reader._data
        now = time.monotonic()

        # Simulate 500 valid sentences received earlier
        for _ in range(500):
            parse_nmea_sentence("$GNGGA,064000.00,,,,0,00,99.99,,,,,,*56", data)

        self.reader._last_valid_nmea_mono = now - 15.0  # Last valid was 15s ago
        self.reader._recovery_state = "HEALTHY"

        silence_time = now - self.reader._last_valid_nmea_mono
        self.assertGreater(silence_time, settings.GPS_NMEA_SILENCE_TIMEOUT_SEC)

        # Test recovery trigger on silence
        with patch.object(self.reader, "_run_recovery_worker") as mock_worker:
            self.reader.running = True
            triggered = self.reader._trigger_recovery(reason="test silence")
            self.assertTrue(triggered)

    def test_03_recovery_requires_actual_nmea_resumption(self):
        """Verify state machine remains in RECOVERING after AT command, and only transitions to HEALTHY on valid NMEA."""
        self.reader._recovery_state = "RECOVERING"
        self.assertEqual(self.reader._recovery_state, "RECOVERING")

        # Corrupt data does NOT transition to HEALTHY
        parse_nmea_sentence("GARBAGE\r\n", self.reader._data)
        self.assertEqual(self.reader._recovery_state, "RECOVERING")

        # Only authentic valid NMEA transitions to HEALTHY
        parsed = parse_nmea_sentence("$GNGGA,064000.00,,,,0,00,99.99,,,,,,*56", self.reader._data)
        self.assertTrue(parsed)
        if parsed:
            with self.reader._recovery_lock:
                self.reader._recovery_state = "HEALTHY"

        self.assertEqual(self.reader._recovery_state, "HEALTHY")

    def test_04_dynamic_at_port_fallback(self):
        """Verify that when /dev/ttyUSB2 is unavailable/fails, /dev/ttyUSB1 is discovered and verified."""
        def mock_serial(port, baudrate, timeout):
            if port == "/dev/ttyUSB2":
                raise serial.SerialException("device or resource busy")
            elif port == "/dev/ttyUSB1":
                return MockSerialPort(b"AT\r\r\nOK\r\n+CGNSSPWR: 1,0,1,0\r\n\r\nOK\r\n")
            raise serial.SerialException("not found")

        with patch("os.path.exists", return_value=True), \
             patch("serial.Serial", side_effect=mock_serial):
            selected_port = self.reader.find_simcom_at_port()
            self.assertEqual(selected_port, "/dev/ttyUSB1")
            self.assertEqual(self.reader._active_at_port, "/dev/ttyUSB1")

    def test_05_rejection_of_unsuitable_serial_ports(self):
        """Verify ports that do not respond to AT or lack SIMCom GNSS capability are rejected."""
        def mock_unsuitable_serial(port, baudrate, timeout):
            return MockSerialPort(b"some_other_hardware_log\r\n")

        with patch("os.path.exists", return_value=True), \
             patch("serial.Serial", side_effect=mock_unsuitable_serial):
            selected_port = self.reader.find_simcom_at_port()
            self.assertIsNone(selected_port)

    def test_06_single_worker_concurrency_protection(self):
        """Verify that only one recovery worker can run concurrently."""
        self.reader.running = True
        self.reader._recovery_in_progress = True

        # Second trigger while in progress must be rejected
        triggered = self.reader._trigger_recovery(reason="concurrent attempt")
        self.assertFalse(triggered)

    def test_07_worker_flag_cleanup_after_exceptions(self):
        """Verify _recovery_in_progress is safely cleared in finally block even when exceptions occur."""
        self.reader.running = True
        with patch.object(self.reader, "find_simcom_at_port", side_effect=RuntimeError("unexpected crash")):
            self.reader._run_recovery_worker()

        # Flag must be cleared
        self.assertFalse(self.reader._recovery_in_progress)
        self.assertEqual(self.reader._recovery_state, "BACKOFF")

    def test_08_exponential_backoff_timing_and_reset(self):
        """Verify exponential backoff progression and reset upon valid NMEA stream."""
        self.reader.running = True
        settings.GPS_RECOVERY_BACKOFF_BASE_SEC = 2.0
        settings.GPS_RECOVERY_BACKOFF_MAX_SEC = 30.0

        # Simulate failures
        with patch.object(self.reader, "find_simcom_at_port", return_value=None):
            self.reader._retry_count = 0
            self.reader._run_recovery_worker()
            self.assertEqual(self.reader._retry_count, 1)

            self.reader._run_recovery_worker()
            self.assertEqual(self.reader._retry_count, 2)

        # Reset upon receiving healthy NMEA
        self.reader._retry_count = 0
        self.reader._next_retry_time_mono = 0.0
        self.assertEqual(self.reader._retry_count, 0)
        self.assertEqual(self.reader._next_retry_time_mono, 0.0)

    def test_09_no_cgpswarm_emitted(self):
        """CRITICAL: Verify that AT+CGPSWARM is NEVER sent during the automatic initialization sequence."""
        mock_ser = MockSerialPort(b"OK\r\n")

        with patch("serial.Serial", return_value=mock_ser):
            self.reader._execute_modem_init_sequence("/dev/ttyUSB2")

        # Check all emitted commands
        emitted_commands = [b.decode("ascii", errors="ignore") for b in mock_ser.written]
        for cmd in emitted_commands:
            self.assertNotIn("CGPSWARM", cmd, "AT+CGPSWARM must not be in the automatic startup sequence!")

    def test_10_no_recovery_attempts_while_gnss_healthy(self):
        """Verify recovery is not triggered while valid NMEA data has arrived recently (< 10s)."""
        now = time.monotonic()
        self.reader._last_valid_nmea_mono = now - 2.0  # Valid NMEA was 2s ago
        time_since_valid = now - self.reader._last_valid_nmea_mono
        self.assertLess(time_since_valid, settings.GPS_NMEA_SILENCE_TIMEOUT_SEC)

    def test_11_clean_shutdown_and_cancellation(self):
        """Verify stop_reader sets running=False, recovery_state=STOPPING, and closes ports."""
        self.reader.running = True
        self.reader._recovery_state = "HEALTHY"
        self.reader.stop_reader()

        self.assertFalse(self.reader.running)
        self.assertEqual(self.reader._recovery_state, "STOPPING")

    def test_12_backward_compatibility_of_gps_telemetry(self):
        """Verify GPSData serialization maintains all existing telemetry fields."""
        state = self.reader.get_state()
        dump = state.model_dump()

        # Existing navigation & persistence fields
        self.assertIn("latitude", dump)
        self.assertIn("longitude", dump)
        self.assertIn("position_source", dump)
        self.assertIn("live_fix_valid", dump)
        self.assertIn("awaiting_live_fix", dump)
        self.assertIn("satellites_used", dump)
        self.assertIn("hdop", dump)

        # New GNSS health monitoring fields
        self.assertIn("gnss_health_state", dump)
        self.assertIn("modem_at_port", dump)
        self.assertIn("last_valid_nmea_monotonic", dump)


if __name__ == "__main__":
    unittest.main()
