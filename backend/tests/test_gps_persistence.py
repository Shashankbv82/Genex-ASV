"""
GENEX ASV - Unit Tests for GPS Persistence and Navigation Safety Isolation (unittest)
"""

import os
import json
import time
import shutil
import tempfile
import unittest
from backend.telemetry.state import GPSData
from backend.gps.persistence import save_last_known_fix, load_last_known_fix, is_valid_coordinate
from backend.gps.filter import AdaptiveCVKalmanFilter

class TestGPSPersistence(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.test_dir, "test_last_gps_fix.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_coordinate_validation(self):
        self.assertTrue(is_valid_coordinate(12.9355, 77.6207))
        self.assertTrue(is_valid_coordinate(-34.6037, -58.3816))
        # Null island
        self.assertFalse(is_valid_coordinate(0.0, 0.0))
        self.assertFalse(is_valid_coordinate(1e-7, 1e-7))
        # None or invalid
        self.assertFalse(is_valid_coordinate(None, 77.62))
        self.assertFalse(is_valid_coordinate(12.93, None))
        self.assertFalse(is_valid_coordinate("invalid", 77.62))
        # Out of range
        self.assertFalse(is_valid_coordinate(95.0, 77.62))
        self.assertFalse(is_valid_coordinate(12.93, 190.0))

    def test_save_and_load_fix(self):
        gps = GPSData(
            latitude=12.9355123,
            longitude=77.6207456,
            altitude_m=912.4,
            speed_mps=1.25,
            course_deg=184.2,
            satellites_used=9,
            hdop=0.85,
            timestamp_utc="081530.00"
        )

        success = save_last_known_fix(gps, self.cache_file)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.cache_file))

        loaded = load_last_known_fix(self.cache_file)
        self.assertIsNotNone(loaded)
        self.assertAlmostEqual(loaded["latitude"], 12.9355123, places=6)
        self.assertAlmostEqual(loaded["longitude"], 77.6207456, places=6)
        self.assertEqual(loaded["altitude_m"], 912.4)
        self.assertEqual(loaded["speed_mps"], 1.25)
        self.assertEqual(loaded["course_deg"], 184.2)
        self.assertEqual(loaded["satellites_used"], 9)
        self.assertEqual(loaded["hdop"], 0.85)
        self.assertIn("saved_at_iso", loaded)
        self.assertIn("saved_at_epoch", loaded)

    def test_atomic_write_leaves_no_temp_files(self):
        gps = GPSData(latitude=13.0827, longitude=80.2707)
        save_last_known_fix(gps, self.cache_file)

        files = os.listdir(self.test_dir)
        tmp_files = [f for f in files if ".tmp." in f]
        self.assertEqual(len(tmp_files), 0)

    def test_load_nonexistent_file(self):
        missing_path = os.path.join(self.test_dir, "non_existent.json")
        result = load_last_known_fix(missing_path)
        self.assertIsNone(result)

    def test_corrupt_file_recovery(self):
        # Empty file
        with open(self.cache_file, "w") as f:
            f.write("")
        self.assertIsNone(load_last_known_fix(self.cache_file))

        # Corrupt JSON
        with open(self.cache_file, "w") as f:
            f.write("{this is not json! 12345")
        self.assertIsNone(load_last_known_fix(self.cache_file))

        # JSON with null coordinates
        with open(self.cache_file, "w") as f:
            json.dump({"latitude": None, "longitude": None}, f)
        self.assertIsNone(load_last_known_fix(self.cache_file))

        # JSON with Null Island (0.0, 0.0)
        with open(self.cache_file, "w") as f:
            json.dump({"latitude": 0.0, "longitude": 0.0}, f)
        self.assertIsNone(load_last_known_fix(self.cache_file))

    def test_safety_isolation_in_kalman_filter(self):
        """
        CRITICAL REQUIREMENT:
        Cached / last-known fixes must NEVER update or initialize the Kalman filter.
        """
        filter_obj = AdaptiveCVKalmanFilter()

        # 1. Provide cached fix (position_source="last_known")
        cached_gps = GPSData(
            position_source="last_known",
            live_fix_valid=False,
            fix_valid=True,
            latitude=12.9355,
            longitude=77.6207,
            satellites_used=8,
            hdop=1.0
        )

        t_now = time.monotonic()
        updated = filter_obj.update(cached_gps, t_now)
        self.assertFalse(updated)
        filtered_pos = filter_obj.get_filtered_position()
        self.assertFalse(filtered_pos.is_filtered)
        self.assertIsNone(filtered_pos.latitude)
        self.assertIsNone(filtered_pos.longitude)

        # 2. Provide authentic live fix (position_source="live", live_fix_valid=True)
        live_gps = GPSData(
            position_source="live",
            live_fix_valid=True,
            fix_valid=True,
            latitude=12.9355,
            longitude=77.6207,
            satellites_used=8,
            hdop=1.0,
            timestamp_utc="081600.00"
        )

        updated_live = filter_obj.update(live_gps, t_now + 1.0)
        self.assertTrue(updated_live)
        filter_obj.predict_to(t_now + 1.2)
        filtered_live = filter_obj.get_filtered_position()
        self.assertTrue(filtered_live.is_filtered)
        self.assertIsNotNone(filtered_live.latitude)
        self.assertAlmostEqual(filtered_live.latitude, 12.9355, places=4)

if __name__ == "__main__":
    unittest.main()
