"""
GENEX ASV - Automated Test Suite for Adaptive Constant-Velocity Kalman Filter
12 comprehensive offline unit tests using standard library unittest.
"""

import math
import time
import threading
import unittest

from backend.config import settings
from backend.gps.filter import (
    AdaptiveCVKalmanFilter,
    wgs84_to_enu,
    enu_to_wgs84,
    CandidateFix,
    WGS84_A
)
from backend.telemetry.state import GPSData

class TestAdaptiveCVKalmanFilter(unittest.TestCase):
    def setUp(self):
        # Always enable filter and use default test settings
        settings.ENABLE_GPS_FILTER = True
        self.filter = AdaptiveCVKalmanFilter()
        self.lat0 = 12.9355690
        self.lon0 = 77.6208100
        self.t0 = 1000.0

    def _make_gps(self, lat, lon, t_mono, speed=0.0, course=0.0, hdop=1.0, sats=8, valid=True, utc="120000.000"):
        return GPSData(
            connected=True,
            fix_valid=valid,
            fix_quality=1 if valid else 0,
            fix_type="3D" if valid else "none",
            latitude=lat,
            longitude=lon,
            altitude_m=900.0,
            speed_mps=speed,
            course_deg=course,
            satellites_used=sats,
            hdop=hdop,
            timestamp_utc=utc,
            last_update_monotonic=t_mono
        )

    def test_01_concurrent_access_thread_lock(self):
        """Test concurrent access from multiple threads without race conditions or deadlock."""
        # Anchor filter
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        stop_event = threading.Event()
        errors = []

        def writer_thread():
            t = self.t0
            i = 0
            while not stop_event.is_set():
                t += 0.2
                i += 1
                gps = self._make_gps(
                    self.lat0 + i * 1e-6,
                    self.lon0 + i * 1e-6,
                    t,
                    speed=0.5,
                    utc=f"1200{i:03d}"
                )
                try:
                    self.filter.update(gps, t)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.005)

        def reader_thread():
            t = self.t0
            while not stop_event.is_set():
                t += 0.05
                try:
                    self.filter.predict_to(t)
                    pos = self.filter.get_filtered_position()
                    self.assertIsNotNone(pos)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.002)

        t1 = threading.Thread(target=writer_thread)
        t2 = threading.Thread(target=reader_thread)
        t1.start()
        t2.start()

        time.sleep(0.3)
        stop_event.set()
        t1.join(timeout=1.0)
        t2.join(timeout=1.0)

        self.assertEqual(len(errors), 0, f"Concurrent thread errors encountered: {errors}")

    def test_02_duplicate_submillisecond_prediction_suppressed(self):
        """Test that dt < 1ms does not mutate state or double-advance covariance."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        p_before = [row[:] for row in self.filter.P]
        x_before = list(self.filter.x)

        # Call predict with dt = 0.0002 (0.2 ms)
        self.filter.predict_to(self.t0 + 0.0002)

        self.assertEqual(self.filter.x, x_before)
        self.assertEqual(self.filter.P, p_before)
        self.assertEqual(self.filter._last_time_mono, self.t0)

    def test_03_repeated_identical_outlier_rejection(self):
        """Test that a repeated identical 50m outlier does not bypass gate or cause false reseed."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # 50m North outlier
        lat_outlier, lon_outlier = enu_to_wgs84(0.0, 50.0, self.lat0, self.lon0)

        # Send outlier 3 times with 1s intervals
        t = self.t0
        for i in range(3):
            t += 1.0
            outlier_gps = self._make_gps(lat_outlier, lon_outlier, t, utc=f"12000{i+1}")
            accepted = self.filter.update(outlier_gps, t)
            self.assertFalse(accepted, f"Outlier {i+1} should have been rejected")

        # Verify filter state did not jump to 50m
        pos = self.filter.get_filtered_position()
        self.assertAlmostEqual(pos.latitude, self.lat0, places=5)
        self.assertEqual(self.filter._reseed_count, 0)
        self.assertEqual(self.filter._rejected_count, 3)

    def test_04_low_speed_course_decoupling(self):
        """Test that when speed < 0.4 m/s, course is decoupled and velocity noise is stationary."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # Speed 0.2 m/s with course 90 deg (East)
        t = self.t0 + 1.0
        slow_gps = self._make_gps(self.lat0, self.lon0, t, speed=0.2, course=90.0, utc="120001")
        self.filter.update(slow_gps, t)

        pos = self.filter.get_filtered_position()
        self.assertEqual(self.filter._mode, "stationary")
        self.assertIsNone(pos.course_deg, "Course must be None when speed < 0.4 m/s")

    def test_05_stationary_jitter_variance_reduction(self):
        """Test that stationary GPS jitter variance is significantly reduced by filter."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # Synthetic stationary jitter dataset (1.5m amplitude oscillation around origin)
        raw_x = []
        filtered_x = []
        t = self.t0

        for i in range(30):
            t += 1.0
            jitter_m = 1.5 * math.sin(i * 0.7) + 0.5 * math.cos(i * 1.3)
            lat_j, lon_j = enu_to_wgs84(jitter_m, 0.0, self.lat0, self.lon0)
            gps = self._make_gps(lat_j, lon_j, t, utc=f"12{i:04d}")
            
            raw_x.append(jitter_m)
            self.filter.update(gps, t)
            
            # Predict at intermediate 5 Hz tick
            self.filter.predict_to(t + 0.2)
            pos = self.filter.get_filtered_position()
            fx, fy = wgs84_to_enu(pos.latitude, pos.longitude, self.lat0, self.lon0)
            filtered_x.append(fx)

        # Compute sample variances
        var_raw = sum(x**2 for x in raw_x) / len(raw_x)
        var_filtered = sum(x**2 for x in filtered_x) / len(filtered_x)

        self.assertLess(var_filtered, var_raw * 0.6,
                        f"Filtered variance {var_filtered:.3f} should be < 60% of raw {var_raw:.3f}")

    def test_06_constant_velocity_movement_and_lag(self):
        """Test constant velocity movement tracking and lag <= 1.0m at 1.0 m/s."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # Simulate vehicle moving North at 1.0 m/s for 15 seconds
        t = self.t0
        v_true = 1.0
        for i in range(1, 16):
            t += 1.0
            true_north = v_true * i
            lat_i, lon_i = enu_to_wgs84(0.0, true_north, self.lat0, self.lon0)
            gps = self._make_gps(lat_i, lon_i, t, speed=v_true, course=0.0, utc=f"120{i:03d}")
            self.filter.update(gps, t)

        pos = self.filter.get_filtered_position()
        fx, fy = wgs84_to_enu(pos.latitude, pos.longitude, self.lat0, self.lon0)
        lag = abs(15.0 - fy)

        self.assertEqual(self.filter._mode, "moving")
        self.assertAlmostEqual(pos.speed_mps, 1.0, delta=0.2)
        self.assertLess(lag, 1.0, f"Dynamic tracking lag {lag:.2f}m exceeds 1.0m limit")

    def test_07_outage_transitions_active_coasting_outage(self):
        """Test state transitions: moving -> coasting (1.5s-3.0s with speed decay) -> outage (>3.0s)."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # Move at 1.0 m/s
        t = self.t0 + 1.0
        gps = self._make_gps(self.lat0, self.lon0, t, speed=1.0, course=0.0, utc="120001")
        self.filter.update(gps, t)
        self.assertEqual(self.filter._mode, "moving")

        # Advance 1.0s without GPS (age = 1.0s <= 1.5s -> active moving)
        t_active = t + 1.0
        self.filter.predict_to(t_active)
        pos = self.filter.get_filtered_position()
        self.assertEqual(pos.diagnostics.filter_mode, "moving")
        self.assertTrue(pos.is_filtered)

        # Advance to age = 2.0s (1.5s < age <= 3.0s -> coasting)
        t_coast = t + 2.0
        self.filter.predict_to(t_coast)
        pos = self.filter.get_filtered_position()
        self.assertEqual(pos.diagnostics.filter_mode, "coasting")
        self.assertTrue(pos.is_filtered)
        self.assertTrue(pos.uncertainty_warning)
        # Verify speed decayed by 5%/s
        self.assertLess(pos.speed_mps, 1.0)

        # Advance to age = 3.5s (> 3.0s -> outage)
        t_outage = t + 3.5
        self.filter.predict_to(t_outage)
        pos = self.filter.get_filtered_position()
        self.assertEqual(pos.diagnostics.filter_mode, "outage")
        self.assertFalse(pos.is_filtered, "is_filtered must be False during outage")

    def test_08_recovery_poor_hdop_rejected(self):
        """Test that outage recovery attempt with poor HDOP or low satellites is rejected."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # Force outage
        self.filter.predict_to(self.t0 + 5.0)
        self.assertEqual(self.filter._mode, "outage")

        # Attempt recovery with poor HDOP (2.8 > 2.0 limit)
        t = self.t0 + 6.0
        poor_gps = self._make_gps(self.lat0, self.lon0, t, hdop=2.8, sats=8, utc="120006")
        accepted = self.filter.update(poor_gps, t)
        self.assertFalse(accepted)
        self.assertEqual(self.filter._mode, "outage")

        # Attempt recovery with poor satellite count (4 < 6 limit)
        poor_sats_gps = self._make_gps(self.lat0, self.lon0, t + 1.0, hdop=1.0, sats=4, utc="120007")
        accepted = self.filter.update(poor_sats_gps, t + 1.0)
        self.assertFalse(accepted)
        self.assertEqual(self.filter._mode, "outage")

    def test_09_recovery_plausible_displacement_accepted(self):
        """Test that valid cluster of 3 fixes after outage successfully triggers reseed."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # Force outage for 15 seconds
        self.filter.predict_to(self.t0 + 15.0)
        self.assertEqual(self.filter._mode, "outage")

        # After 15s outage, vehicle moved 15m North (1.0 m/s average speed is plausible)
        lat_rec, lon_rec = enu_to_wgs84(0.0, 15.0, self.lat0, self.lon0)
        t = self.t0 + 15.0

        for i in range(3):
            t += 1.0
            # Cluster tightly within 0.2m
            lat_c, lon_c = enu_to_wgs84(0.1 * i, 15.0 + 0.1 * i, self.lat0, self.lon0)
            gps = self._make_gps(lat_c, lon_c, t, hdop=1.0, sats=8, utc=f"12001{i+6}")
            accepted = self.filter.update(gps, t)
            if i < 2:
                self.assertFalse(accepted, f"Fix {i+1} should be buffered, not yet reseeded")
            else:
                self.assertTrue(accepted, "Fix 3 should complete cluster and trigger reseed")

        pos = self.filter.get_filtered_position()
        self.assertEqual(self.filter._mode, "recovery")
        self.assertEqual(self.filter._reseed_count, 1)
        self.assertTrue(pos.is_filtered)
        self.assertAlmostEqual(pos.latitude, lat_rec, places=5)

    def test_10_implausible_jump_rejected(self):
        """Test that a 30m position jump within 1 second is rejected even if repeated."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # At t + 1.0s, position suddenly jumps 30m North (max speed 3.5 m/s cannot do 30m in 1s)
        lat_jump, lon_jump = enu_to_wgs84(0.0, 30.0, self.lat0, self.lon0)
        t = self.t0 + 1.0

        for i in range(3):
            t += 0.2
            gps = self._make_gps(lat_jump, lon_jump, t, hdop=1.0, sats=8, utc=f"12000{i+1}")
            accepted = self.filter.update(gps, t)
            self.assertFalse(accepted, f"Implausible jump {i+1} must not be accepted")

        self.assertEqual(self.filter._reseed_count, 0)
        pos = self.filter.get_filtered_position()
        self.assertAlmostEqual(pos.latitude, self.lat0, places=5)

    def test_11_cluster_spread_radius_enforcement(self):
        """Test that candidates with pairwise distance > 2.5m fail spread check and do not reseed."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)

        # Force outage
        self.filter.predict_to(self.t0 + 10.0)
        self.assertEqual(self.filter._mode, "outage")

        # Send 3 candidates with spread > 2.5m (e.g. 0m, 2.0m, 4.0m)
        t = self.t0 + 10.0
        offsets = [0.0, 2.0, 4.0]
        for i, off in enumerate(offsets):
            t += 1.0
            lat_s, lon_s = enu_to_wgs84(0.0, 15.0 + off, self.lat0, self.lon0)
            gps = self._make_gps(lat_s, lon_s, t, hdop=1.0, sats=8, utc=f"12001{i+1}")
            accepted = self.filter.update(gps, t)
            self.assertFalse(accepted, f"Candidate {i+1} with excessive spread should not reseed")

        self.assertEqual(self.filter._reseed_count, 0)
        self.assertEqual(self.filter._mode, "outage")

    def test_12_accepted_measurement_timestamp_tracking(self):
        """Test that _last_accepted_fix_time_mono is only updated on accepted fixes, not outliers."""
        init_gps = self._make_gps(self.lat0, self.lon0, self.t0)
        self.filter.update(init_gps, self.t0)
        self.assertEqual(self.filter._last_accepted_fix_time_mono, self.t0)

        # Send outlier at t0 + 1.0s
        lat_outlier, lon_outlier = enu_to_wgs84(0.0, 60.0, self.lat0, self.lon0)
        outlier_gps = self._make_gps(lat_outlier, lon_outlier, self.t0 + 1.0, utc="120001")
        self.filter.update(outlier_gps, self.t0 + 1.0)
        self.assertEqual(self.filter._last_accepted_fix_time_mono, self.t0,
                         "Accepted timestamp must NOT update on rejected outlier")

        # Send valid fix at t0 + 2.0s
        valid_gps = self._make_gps(self.lat0, self.lon0, self.t0 + 2.0, utc="120002")
        self.filter.update(valid_gps, self.t0 + 2.0)
        self.assertEqual(self.filter._last_accepted_fix_time_mono, self.t0 + 2.0,
                         "Accepted timestamp MUST update on accepted fix")

if __name__ == "__main__":
    unittest.main()
