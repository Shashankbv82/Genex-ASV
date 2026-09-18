"""
GENEX ASV - Adaptive Constant-Velocity Kalman Filter (Local ENU)
Provides low-latency, jitter-free position estimation for ASV UI display.
Thread-safe, decoupled 2D innovation gating, candidate clustering, and outage state machine.
"""

import math
import time
import logging
import threading
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

from backend.config import settings
from backend.telemetry.state import GPSData, FilteredPosition, FilterDiagnostics

logger = logging.getLogger("genex.gps.filter")

# WGS84 Constants
WGS84_A = 6378137.0  # semi-major axis (meters)

def wgs84_to_enu(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    """Projects WGS84 lat/lon to local Cartesian East-North-Up (meters)."""
    phi0 = math.radians(lat0)
    phi = math.radians(lat)
    lam = math.radians(lon)
    lam0 = math.radians(lon0)
    
    x_east = (lam - lam0) * math.cos(phi0) * WGS84_A
    y_north = (phi - phi0) * WGS84_A
    return x_east, y_north

def enu_to_wgs84(x: float, y: float, lat0: float, lon0: float) -> Tuple[float, float]:
    """Inverse projection from local ENU (meters) back to WGS84 lat/lon degrees."""
    phi0 = math.radians(lat0)
    d_lat = y / WGS84_A
    d_lon = x / (WGS84_A * math.cos(phi0)) if abs(math.cos(phi0)) > 1e-8 else 0.0
    
    lat = lat0 + math.degrees(d_lat)
    lon = lon0 + math.degrees(d_lon)
    return lat, lon

@dataclass
class CandidateFix:
    t_mono: float
    enu_x: float
    enu_y: float
    lat: float
    lon: float
    speed_mps: float
    course_deg: float
    hdop: float
    satellites_used: int
    fix_valid: bool
    fix_quality: int

class AdaptiveCVKalmanFilter:
    def __init__(self):
        self._lock = threading.Lock()
        
        # State vector: [p_e, p_n, v_e, v_n]^T
        self.x = [0.0, 0.0, 0.0, 0.0]
        
        # Covariance matrix 4x4 (stored as list of 4 lists)
        self.P = [
            [25.0, 0.0,  0.0,  0.0],
            [0.0, 25.0,  0.0,  0.0],
            [0.0,  0.0,  4.0,  0.0],
            [0.0,  0.0,  0.0,  4.0]
        ]
        
        # Local origin anchor
        self._origin_lat: Optional[float] = None
        self._origin_lon: Optional[float] = None
        
        # Timing invariant
        self._last_time_mono: Optional[float] = None
        self._last_accepted_fix_time_mono: Optional[float] = None
        self._last_raw_seen_time_mono: Optional[float] = None
        
        # Operational mode: init | stationary | moving | coasting | outage | recovery | disabled
        self._mode = "init"
        
        # Diagnostics
        self._rejected_count = 0
        self._accepted_count = 0
        self._reseed_count = 0
        self._last_reseed_reason: Optional[str] = None
        self._last_innovation_dist_m: Optional[float] = None
        self._last_displacement_m: Optional[float] = None
        
        # Candidate cluster buffer for verified reseeding
        self._candidates: List[CandidateFix] = []
        
        # Track last processed raw timestamp to prevent duplicate measurements
        self._last_processed_utc: Optional[str] = None
        self._last_processed_monotonic: float = 0.0

    def reset(self):
        """Resets filter to uninitialized state."""
        with self._lock:
            self._mode = "init"
            self.x = [0.0, 0.0, 0.0, 0.0]
            self.P = [
                [25.0, 0.0,  0.0,  0.0],
                [0.0, 25.0,  0.0,  0.0],
                [0.0,  0.0,  4.0,  0.0],
                [0.0,  0.0,  0.0,  4.0]
            ]
            self._origin_lat = None
            self._origin_lon = None
            self._last_time_mono = None
            self._last_accepted_fix_time_mono = None
            self._last_raw_seen_time_mono = None
            self._candidates.clear()
            self._last_innovation_dist_m = None
            self._last_displacement_m = None
            self._last_processed_utc = None
            self._last_processed_monotonic = 0.0

    def _predict_step(self, dt: float):
        """Pure prediction step along state transition matrix F and process noise Q."""
        if dt <= 0.0:
            return

        # Adaptive acceleration noise spectral density based on mode and speed
        speed = math.hypot(self.x[2], self.x[3])
        if self._mode == "coasting":
            # Coasting speed decay: 5% per second
            decay = max(0.0, 1.0 - 0.05 * dt)
            self.x[2] *= decay
            self.x[3] *= decay
            sigma_a = settings.GPS_FILTER_STATIONARY_ACCEL_SIGMA
        elif speed < settings.GPS_FILTER_COURSE_MIN_SPEED:
            sigma_a = settings.GPS_FILTER_STATIONARY_ACCEL_SIGMA
            # When stationary, gently bleed off residual velocity
            self.x[2] *= max(0.0, 1.0 - 0.2 * dt)
            self.x[3] *= max(0.0, 1.0 - 0.2 * dt)
        else:
            sigma_a = settings.GPS_FILTER_MOVING_ACCEL_SIGMA

        q = sigma_a * sigma_a

        # State extrapolation: x = F * x
        # p_e = p_e + v_e * dt
        # p_n = p_n + v_n * dt
        self.x[0] += self.x[2] * dt
        self.x[1] += self.x[3] * dt

        # Continuous white noise acceleration process noise covariance Q
        dt2 = dt * dt
        dt3 = dt2 * dt
        q11 = q * dt3 / 3.0
        q12 = q * dt2 / 2.0
        q22 = q * dt

        # Covariance propagation: P = F * P * F^T + Q
        p = self.P

        # Compute F * P
        fp = [
            [p[0][c] + dt * p[2][c] for c in range(4)],
            [p[1][c] + dt * p[3][c] for c in range(4)],
            [p[2][c] for c in range(4)],
            [p[3][c] for c in range(4)]
        ]

        # Compute (F * P) * F^T + Q
        self.P = [
            [fp[0][0] + dt * fp[0][2] + q11, fp[0][1] + dt * fp[0][3],       fp[0][2] + q12,                 fp[0][3]],
            [fp[1][0] + dt * fp[1][2],       fp[1][1] + dt * fp[1][3] + q11, fp[1][2],                       fp[1][3] + q12],
            [fp[2][0] + dt * fp[2][2] + q12, fp[2][1] + dt * fp[2][3],       fp[2][2] + q22,                 fp[2][3]],
            [fp[3][0] + dt * fp[3][2],       fp[3][1] + dt * fp[3][3] + q12, fp[3][2],                       fp[3][3] + q22]
        ]

        # Enforce exact numerical symmetry
        for i in range(4):
            for j in range(i + 1, 4):
                val = 0.5 * (self.P[i][j] + self.P[j][i])
                self.P[i][j] = val
                self.P[j][i] = val

    def predict_to(self, t_now_mono: float):
        """Advances filter time-update to t_now_mono exactly once."""
        with self._lock:
            if not settings.ENABLE_GPS_FILTER:
                return

            if self._last_time_mono is None:
                self._last_time_mono = t_now_mono
                return

            dt = t_now_mono - self._last_time_mono
            if dt < 0.001:
                return  # Skip duplicate or sub-millisecond intervals

            dt = min(dt, 2.0)  # Clamp against system pause
            
            # Update outage state machine prior to prediction step so coasting decay takes effect
            self._update_outage_state(t_now_mono)
            self._predict_step(dt)
            self._last_time_mono = t_now_mono

    def _update_outage_state(self, t_now_mono: float):
        """Evaluates outage/coasting transitions based on accepted fix age."""
        if self._mode == "init" or self._mode == "disabled":
            return

        if self._last_accepted_fix_time_mono is None:
            self._mode = "outage"
            return

        dt_since_accepted = t_now_mono - self._last_accepted_fix_time_mono

        if dt_since_accepted <= 1.5:
            # Active tracking
            speed = math.hypot(self.x[2], self.x[3])
            self._mode = "moving" if speed >= settings.GPS_FILTER_COURSE_MIN_SPEED else "stationary"
        elif dt_since_accepted <= settings.GPS_FILTER_MAX_COAST_SEC:
            self._mode = "coasting"
        else:
            self._mode = "outage"

    def _check_reseed_candidate(self, cand: CandidateFix, t_now: float) -> Tuple[bool, Optional[str]]:
        """Quality-aware check on candidate cluster to confirm genuine recovery/movement."""
        # 1. Quality validation
        if not cand.fix_valid or cand.fix_quality < 1:
            return False, "invalid_fix"
        if cand.satellites_used < 6:
            return False, "insufficient_sats"
        if cand.hdop > 2.0:
            return False, "poor_hdop"

        # 2. Candidate buffering & expiry
        self._candidates.append(cand)
        # Purge candidates older than 5.0 seconds
        self._candidates = [c for c in self._candidates if (t_now - c.t_mono) <= 5.0]

        # Require minimum consistent cluster size
        if len(self._candidates) < settings.GPS_FILTER_RESEED_CLUSTER_SIZE:
            return False, f"buffering_cluster_{len(self._candidates)}/{settings.GPS_FILTER_RESEED_CLUSTER_SIZE}"

        # 3. Cluster spread enforcement
        # Max pairwise distance between any two candidates in buffer
        max_spread = 0.0
        for i in range(len(self._candidates)):
            for j in range(i + 1, len(self._candidates)):
                d = math.hypot(self._candidates[i].enu_x - self._candidates[j].enu_x,
                               self._candidates[i].enu_y - self._candidates[j].enu_y)
                if d > max_spread:
                    max_spread = d

        if max_spread > settings.GPS_FILTER_RESEED_MAX_RADIUS_M:
            return False, f"cluster_spread_exceeded_{max_spread:.2f}m"

        # 4. Physical Plausibility vs Elapsed Time
        # Time since last accepted measurement
        dt_accepted = (t_now - self._last_accepted_fix_time_mono) if self._last_accepted_fix_time_mono else 999.0
        
        # Center of cluster
        avg_x = sum(c.enu_x for c in self._candidates) / len(self._candidates)
        avg_y = sum(c.enu_y for c in self._candidates) / len(self._candidates)
        jump_dist = math.hypot(avg_x - self.x[0], avg_y - self.x[1])

        max_plausible_dist = (settings.GPS_FILTER_MAX_ASV_SPEED_MPS * dt_accepted) + (3.0 * cand.hdop) + 3.0

        if dt_accepted < 10.0 and jump_dist > max_plausible_dist:
            # Unexplained massive jump in a short window without an outage -> reject!
            return False, f"implausible_jump_{jump_dist:.1f}m_in_{dt_accepted:.1f}s"

        return True, "cluster_verified"

    def _execute_reseed(self, cand: CandidateFix, t_now: float, reason: str):
        """Safely re-seeds state vector to verified candidate location."""
        disp = math.hypot(cand.enu_x - self.x[0], cand.enu_y - self.x[1])
        
        logger.warning(
            "GPS_FILTER_RESEED: Filter reseeded to (lat=%.7f, lon=%.7f). "
            "Displacement=%.2fm, Sats=%d, HDOP=%.2f, Reason=%s",
            cand.lat, cand.lon, disp, cand.satellites_used, cand.hdop, reason
        )

        self.x[0] = cand.enu_x
        self.x[1] = cand.enu_y
        self.x[2] = 0.0
        self.x[3] = 0.0

        # Reset covariance to measurement error
        pos_var = max(4.0, (2.5 * cand.hdop) ** 2)
        self.P = [
            [pos_var, 0.0,     0.0, 0.0],
            [0.0,     pos_var, 0.0, 0.0],
            [0.0,     0.0,     1.0, 0.0],
            [0.0,     0.0,     0.0, 1.0]
        ]

        self._reseed_count += 1
        self._last_reseed_reason = reason
        self._last_displacement_m = round(disp, 2)
        self._rejected_count = 0
        self._candidates.clear()
        self._last_accepted_fix_time_mono = t_now
        self._mode = "recovery"

    def update(self, raw_gps: GPSData, t_now_mono: float) -> bool:
        """Processes an incoming raw GNSS observation."""
        with self._lock:
            if not settings.ENABLE_GPS_FILTER:
                self._mode = "disabled"
                return False

            self._last_raw_seen_time_mono = t_now_mono

            # Check if fix is valid
            if not raw_gps.fix_valid or raw_gps.latitude is None or raw_gps.longitude is None:
                self._update_outage_state(t_now_mono)
                return False

            # Check for duplicate measurement within same epoch
            if raw_gps.timestamp_utc and raw_gps.timestamp_utc == self._last_processed_utc:
                if raw_gps.last_update_monotonic > 0 and raw_gps.last_update_monotonic == self._last_processed_monotonic:
                    return False

            # Initialize local origin on first valid 3D fix
            if self._origin_lat is None or self._origin_lon is None:
                if (raw_gps.satellites_used or 0) >= 5 and (raw_gps.hdop or 99.0) <= 2.5:
                    self._origin_lat = raw_gps.latitude
                    self._origin_lon = raw_gps.longitude
                    self.x = [0.0, 0.0, 0.0, 0.0]
                    self._last_time_mono = t_now_mono
                    self._last_accepted_fix_time_mono = t_now_mono
                    self._last_processed_utc = raw_gps.timestamp_utc
                    self._last_processed_monotonic = raw_gps.last_update_monotonic
                    self._mode = "stationary"
                    logger.info("GPS_FILTER_INIT: Anchored local ENU at (%.7f, %.7f)", self._origin_lat, self._origin_lon)
                    return True
                return False

            # 1. Prediction up to current measurement timestamp
            if self._last_time_mono is not None:
                dt = t_now_mono - self._last_time_mono
                if dt > 0.001:
                    dt = min(dt, 2.0)
                    self._predict_step(dt)
                    self._last_time_mono = t_now_mono

            # 2. Project observation to local ENU
            zx, zy = wgs84_to_enu(raw_gps.latitude, raw_gps.longitude, self._origin_lat, self._origin_lon)
            speed_raw = raw_gps.speed_mps or 0.0
            course_raw = raw_gps.course_deg or 0.0

            cand = CandidateFix(
                t_mono=t_now_mono,
                enu_x=zx,
                enu_y=zy,
                lat=raw_gps.latitude,
                lon=raw_gps.longitude,
                speed_mps=speed_raw,
                course_deg=course_raw,
                hdop=raw_gps.hdop or 2.0,
                satellites_used=raw_gps.satellites_used or 0,
                fix_valid=raw_gps.fix_valid,
                fix_quality=raw_gps.fix_quality
            )

            # Check if we are in an outage or recovery mode
            if self._mode in ("outage", "recovery"):
                can_reseed, reason = self._check_reseed_candidate(cand, t_now_mono)
                if can_reseed:
                    self._execute_reseed(cand, t_now_mono, reason)
                    self._last_processed_utc = raw_gps.timestamp_utc
                    self._last_processed_monotonic = raw_gps.last_update_monotonic
                    return True
                return False

            # 3. Decoupled 2D Position Innovation Gate
            # y_pos = z_pos - H_pos * x
            y0 = zx - self.x[0]
            y1 = zy - self.x[1]

            hdop = max(0.8, raw_gps.hdop if raw_gps.hdop is not None else 2.0)
            r_pos = max(1.5, 2.5 * hdop) ** 2
            
            # Innovation covariance S_pos = P_pos + R_pos (2x2)
            s00 = self.P[0][0] + r_pos
            s01 = self.P[0][1]
            s10 = self.P[1][0]
            s11 = self.P[1][1] + r_pos

            det_s = s00 * s11 - s01 * s10
            if det_s <= 1e-9:
                return False

            inv_s00 = s11 / det_s
            inv_s01 = -s01 / det_s
            inv_s10 = -s10 / det_s
            inv_s11 = s00 / det_s

            # Mahalanobis distance squared: d_pos^2 = y^T * S^-1 * y
            d_pos_sq = y0 * (inv_s00 * y0 + inv_s01 * y1) + y1 * (inv_s10 * y0 + inv_s11 * y1)
            self._last_innovation_dist_m = round(math.sqrt(max(0.0, d_pos_sq)), 2)

            # Gate test: threshold 9.21 (Chi-square 2-DOF, p=0.01)
            if d_pos_sq > settings.GPS_FILTER_GATE_THRESHOLD:
                self._rejected_count += 1
                logger.debug("GPS_FILTER_GATE_REJECT: d_sq=%.2f > %.2f, (zx=%.1f, zy=%.1f)",
                             d_pos_sq, settings.GPS_FILTER_GATE_THRESHOLD, zx, zy)
                
                # Test if rejected measurements represent a genuine persistent cluster
                can_reseed, reason = self._check_reseed_candidate(cand, t_now_mono)
                if can_reseed:
                    self._execute_reseed(cand, t_now_mono, reason)
                    self._last_processed_utc = raw_gps.timestamp_utc
                    self._last_processed_monotonic = raw_gps.last_update_monotonic
                    return True
                return False

            # Observation passed position gate! Clear rejected cluster buffer
            self._candidates.clear()
            self._last_displacement_m = round(math.hypot(y0, y1), 2)

            # 4. Decoupled 2D Velocity Evaluation (Low-speed decoupling)
            use_velocity = False
            r_vel = (0.35) ** 2
            zv_e = 0.0
            zv_n = 0.0

            if speed_raw >= settings.GPS_FILTER_COURSE_MIN_SPEED:
                c_rad = math.radians(course_raw)
                zv_e = speed_raw * math.sin(c_rad)
                zv_n = speed_raw * math.cos(c_rad)

                yv0 = zv_e - self.x[2]
                yv1 = zv_n - self.x[3]

                sv00 = self.P[2][2] + r_vel
                sv01 = self.P[2][3]
                sv10 = self.P[3][2]
                sv11 = self.P[3][3] + r_vel

                det_sv = sv00 * sv11 - sv01 * sv10
                if det_sv > 1e-9:
                    inv_sv00 = sv11 / det_sv
                    inv_sv01 = -sv01 / det_sv
                    inv_sv10 = -sv10 / det_sv
                    inv_sv11 = sv00 / det_sv

                    d_vel_sq = yv0 * (inv_sv00 * yv0 + inv_sv01 * yv1) + yv1 * (inv_sv10 * yv0 + inv_sv11 * yv1)
                    if d_vel_sq <= settings.GPS_FILTER_GATE_THRESHOLD:
                        use_velocity = True

            # 5. Apply Kalman Correction
            # Position measurement update:
            # K_pos = P * H_pos^T * S_pos^-1
            # H_pos = [ [1,0,0,0], [0,1,0,0] ]
            # P * H_pos^T has 4 rows, 2 cols: row i is [P[i][0], P[i][1]]
            k_pos = []
            for i in range(4):
                k0 = self.P[i][0] * inv_s00 + self.P[i][1] * inv_s10
                k1 = self.P[i][0] * inv_s01 + self.P[i][1] * inv_s11
                k_pos.append((k0, k1))

            # State update for position: x = x + K_pos * y_pos
            for i in range(4):
                self.x[i] += k_pos[i][0] * y0 + k_pos[i][1] * y1

            # Covariance update: P = (I - K_pos * H_pos) * P
            new_p = [[0.0]*4 for _ in range(4)]
            for i in range(4):
                for j in range(4):
                    sub = k_pos[i][0] * self.P[0][j] + k_pos[i][1] * self.P[1][j]
                    new_p[i][j] = self.P[i][j] - sub
            self.P = new_p

            # Velocity measurement update (if velocity gate passed)
            if use_velocity:
                yv0 = zv_e - self.x[2]
                yv1 = zv_n - self.x[3]

                sv00 = self.P[2][2] + r_vel
                sv01 = self.P[2][3]
                sv10 = self.P[3][2]
                sv11 = self.P[3][3] + r_vel
                det_sv = sv00 * sv11 - sv01 * sv10

                if det_sv > 1e-9:
                    inv_sv00 = sv11 / det_sv
                    inv_sv01 = -sv01 / det_sv
                    inv_sv10 = -sv10 / det_sv
                    inv_sv11 = sv00 / det_sv

                    k_vel = []
                    for i in range(4):
                        k0 = self.P[i][2] * inv_sv00 + self.P[i][3] * inv_sv10
                        k1 = self.P[i][2] * inv_sv01 + self.P[i][3] * inv_sv11
                        k_vel.append((k0, k1))

                    for i in range(4):
                        self.x[i] += k_vel[i][0] * yv0 + k_vel[i][1] * yv1

                    new_p = [[0.0]*4 for _ in range(4)]
                    for i in range(4):
                        for j in range(4):
                            sub = k_vel[i][0] * self.P[2][j] + k_vel[i][1] * self.P[3][j]
                            new_p[i][j] = self.P[i][j] - sub
                    self.P = new_p

            # Enforce symmetry and positive variance
            for i in range(4):
                self.P[i][i] = max(0.01, self.P[i][i])
                for j in range(i + 1, 4):
                    sym = 0.5 * (self.P[i][j] + self.P[j][i])
                    self.P[i][j] = sym
                    self.P[j][i] = sym

            self._accepted_count += 1
            self._last_accepted_fix_time_mono = t_now_mono
            self._last_processed_utc = raw_gps.timestamp_utc
            self._last_processed_monotonic = raw_gps.last_update_monotonic
            
            speed = math.hypot(self.x[2], self.x[3])
            self._mode = "moving" if speed >= settings.GPS_FILTER_COURSE_MIN_SPEED else "stationary"
            return True

    def get_filtered_position(self) -> FilteredPosition:
        """Constructs and returns current FilteredPosition snapshot."""
        with self._lock:
            t_now = time.monotonic()
            
            # Compute age since last ACCEPTED measurement
            if self._last_accepted_fix_time_mono is not None:
                gnss_age = round(t_now - self._last_accepted_fix_time_mono, 2)
            else:
                gnss_age = 999.0

            diag = FilterDiagnostics(
                filter_mode=self._mode,
                innovation_distance_m=self._last_innovation_dist_m,
                rejected_count=self._rejected_count,
                accepted_count=self._accepted_count,
                reseed_count=self._reseed_count,
                last_reseed_reason=self._last_reseed_reason,
                gnss_age_seconds=gnss_age,
                displacement_m=self._last_displacement_m
            )

            # Filter disabled or uninitialized
            if not settings.ENABLE_GPS_FILTER or self._mode == "disabled":
                diag.filter_mode = "disabled"
                return FilteredPosition(is_filtered=False, diagnostics=diag)

            if self._mode in ("init", "outage") or self._origin_lat is None or self._origin_lon is None:
                return FilteredPosition(is_filtered=False, diagnostics=diag)

            # Valid filtered coordinates available
            lat, lon = enu_to_wgs84(self.x[0], self.x[1], self._origin_lat, self._origin_lon)
            speed = round(math.hypot(self.x[2], self.x[3]), 2)
            
            # Course calculation from velocity
            if speed >= settings.GPS_FILTER_COURSE_MIN_SPEED:
                course = round(math.degrees(math.atan2(self.x[2], self.x[3])) % 360.0, 1)
            else:
                course = None

            is_filtered = (self._mode in ("stationary", "moving", "coasting", "recovery"))
            uncertainty_warning = (self._mode in ("coasting", "recovery"))

            return FilteredPosition(
                latitude=round(lat, 7),
                longitude=round(lon, 7),
                speed_mps=speed,
                course_deg=course,
                is_filtered=is_filtered,
                uncertainty_warning=uncertainty_warning,
                diagnostics=diag
            )

# Singleton global instance
gps_filter = AdaptiveCVKalmanFilter()
