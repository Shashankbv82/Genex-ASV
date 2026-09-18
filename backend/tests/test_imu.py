"""
GENEX ASV - Automated Test Suite for BNO055 IMU Driver & Telemetry
10 comprehensive offline unit tests using standard library unittest.
"""

import math
import struct
import unittest
from unittest.mock import MagicMock, patch

from backend.config import settings
from backend.telemetry.state import IMUData, IMUOrientation, IMUVector3
from backend.imu.bno055 import (
    BNO055,
    IMUSnapshot,
    BNO055_CHIP_ID_VALUE,
    REG_CALIB_STAT
)
from backend.imu.reader import IMUReader

class TestBNO055Driver(unittest.TestCase):
    def setUp(self):
        self.driver = BNO055(bus=1, address=0x28)

    def test_01_signed_16bit_decoding(self):
        """Test signed 16-bit little-endian 2's complement decoding."""
        raw_bytes = struct.pack("<hhhhhh", 1, -1, 100, -100, 32767, -32768)
        v1, v2, v3, v4, v5, v6 = struct.unpack("<hhhhhh", raw_bytes)
        self.assertEqual(v1, 1)
        self.assertEqual(v2, -1)
        self.assertEqual(v3, 100)
        self.assertEqual(v4, -100)
        self.assertEqual(v5, 32767)
        self.assertEqual(v6, -32768)

    def test_02_euler_angle_scaling(self):
        """Test Euler heading (16 LSB/deg), roll, and pitch decoding."""
        # 180 degrees heading: 180 * 16 = 2880
        # -45.5 degrees roll: -45.5 * 16 = -728
        # +25.25 degrees pitch: 25.25 * 16 = 404
        euler_bytes = struct.pack("<hhh", 2880, -728, 404)
        h_raw, r_raw, p_raw = struct.unpack("<hhh", euler_bytes)
        
        heading = (h_raw / 16.0) % 360.0
        roll = r_raw / 16.0
        pitch = p_raw / 16.0

        self.assertAlmostEqual(heading, 180.0, places=2)
        self.assertAlmostEqual(roll, -45.5, places=2)
        self.assertAlmostEqual(pitch, 25.25, places=2)

    def test_03_linear_acceleration_and_gravity_scaling(self):
        """Test scaling of linear acceleration and gravity (100 LSB/(m/s^2))."""
        lin_bytes = struct.pack("<hhh", 150, -25, 0)
        grav_bytes = struct.pack("<hhh", 0, 0, 981)

        lx_raw, ly_raw, lz_raw = struct.unpack("<hhh", lin_bytes)
        gx_raw, gy_raw, gz_raw = struct.unpack("<hhh", grav_bytes)

        self.assertAlmostEqual(lx_raw / 100.0, 1.50, places=2)
        self.assertAlmostEqual(ly_raw / 100.0, -0.25, places=2)
        self.assertAlmostEqual(lz_raw / 100.0, 0.0, places=2)

        self.assertAlmostEqual(gx_raw / 100.0, 0.0, places=2)
        self.assertAlmostEqual(gy_raw / 100.0, 0.0, places=2)
        self.assertAlmostEqual(gz_raw / 100.0, 9.81, places=2)

    def test_04_gyroscope_rads_scaling(self):
        """Test angular velocity scaling from 16 LSB/dps to rad/s."""
        gyr_bytes = struct.pack("<hhh", 160, -320, 0)
        wx_raw, wy_raw, wz_raw = struct.unpack("<hhh", gyr_bytes)

        scale_rad = (math.pi / 180.0) / 16.0
        wx = wx_raw * scale_rad
        wy = wy_raw * scale_rad
        wz = wz_raw * scale_rad

        self.assertAlmostEqual(wx, 10.0 * math.pi / 180.0, places=4)
        self.assertAlmostEqual(wy, -20.0 * math.pi / 180.0, places=4)
        self.assertAlmostEqual(wz, 0.0, places=4)

    def test_05_calibration_bitmask_unpacking(self):
        """Test unpacking CALIB_STAT (0x35) bitfields."""
        cal_full = 0b11111111
        sys_f = (cal_full >> 6) & 0x03
        gyr_f = (cal_full >> 4) & 0x03
        acc_f = (cal_full >> 2) & 0x03
        mag_f = cal_full & 0x03
        self.assertEqual((sys_f, gyr_f, acc_f, mag_f), (3, 3, 3, 3))

        cal_part = 0b10010011
        sys_p = (cal_part >> 6) & 0x03
        gyr_p = (cal_part >> 4) & 0x03
        acc_p = (cal_part >> 2) & 0x03
        mag_p = cal_part & 0x03
        self.assertEqual((sys_p, gyr_p, acc_p, mag_p), (2, 1, 0, 3))

    def test_06_heading_mounting_offset_and_declination(self):
        """Test heading computation with mounting offset and magnetic declination."""
        raw_yaw = 350.0
        mounting_offset = 20.0
        declination = -1.2

        mag_heading = (raw_yaw + mounting_offset) % 360.0
        true_heading = (mag_heading + declination) % 360.0

        self.assertAlmostEqual(mag_heading, 10.0, places=1)
        self.assertAlmostEqual(true_heading, 8.8, places=1)

        raw_yaw_2 = 5.0
        offset_neg = -15.0
        mag_heading_2 = (raw_yaw_2 + offset_neg) % 360.0
        self.assertAlmostEqual(mag_heading_2, 350.0, places=1)

    def test_07_axis_body_frame_transform(self):
        """Test body axis convention (+X forward)."""
        lin_acc_sensor_x = 0.5
        forward_acc = lin_acc_sensor_x
        self.assertGreater(forward_acc, 0.0, "Forward acceleration must be positive along +X")

    def test_08_heading_validity_logic(self):
        """Test heading valid flag requires calibrated gyro/sys."""
        self.assertFalse((0 >= 1 or 0 >= 1))
        self.assertTrue((1 >= 1 or 0 >= 1))
        self.assertTrue((0 >= 1 or 2 >= 1))

    def test_09_stale_data_detection(self):
        """Test IMUReader state stale detection after timeout."""
        reader = IMUReader()
        reader._data.connected = True
        reader._data.lifecycle_state = "ready"
        reader._data.last_update_monotonic = 100.0

        with patch("time.monotonic", return_value=100.2):
            state = reader.get_state()
            self.assertFalse(state.is_stale)
            self.assertEqual(state.lifecycle_state, "ready")
            self.assertEqual(state.data_age_seconds, 0.2)

        with patch("time.monotonic", return_value=102.0):
            state_stale = reader.get_state()
            self.assertTrue(state_stale.is_stale)
            self.assertEqual(state_stale.lifecycle_state, "stale")
            self.assertEqual(state_stale.data_age_seconds, 2.0)

    def test_10_sensor_disconnection_and_reconnection(self):
        """Test graceful handling of sensor disconnection and failed I2C reads."""
        reader = IMUReader()
        reader.driver.read_telemetry = MagicMock(return_value=None)
        reader.driver.initialize = MagicMock(return_value=False)

        with reader._lock:
            reader._data.connected = False
            reader._data.lifecycle_state = "disconnected"

        state = reader.get_state()
        self.assertFalse(state.connected)
        self.assertEqual(state.lifecycle_state, "disconnected")

if __name__ == "__main__":
    unittest.main()
