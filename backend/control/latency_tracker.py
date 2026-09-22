"""
GENEX ASV - End-to-End Control Pipeline Latency Instrumentation
Tracks high-resolution monotonic timestamps across all stages:
  1. IBUS frame received (GPIO interrupt / gap detection)
  2. Frame decoded & checksum verified
  3. RCReader update & SignalProcessor normalization
  4. ManualModeController safety & arming evaluation
  5. DifferentialDriveMixer calculation
  6. MotorController PWM conversion
  7. PCA9685 I2C hardware register write
"""

import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional


class LatencyTracker:
    """Thread-safe, low-overhead latency statistics collector for the RC control pipeline."""

    def __init__(self, max_samples: int = 1000) -> None:
        self._lock = threading.Lock()
        self.max_samples = max_samples

        # Rolling sample deques (all values in milliseconds)
        self.decoder_latency_ms: deque = deque(maxlen=max_samples)
        self.rcreader_latency_ms: deque = deque(maxlen=max_samples)
        self.manual_ctrl_latency_ms: deque = deque(maxlen=max_samples)
        self.mixer_latency_ms: deque = deque(maxlen=max_samples)
        self.motor_ctrl_latency_ms: deque = deque(maxlen=max_samples)
        self.pca9685_write_latency_ms: deque = deque(maxlen=max_samples)
        self.total_pipeline_latency_ms: deque = deque(maxlen=max_samples)

        # Frame counter
        self.sample_count: int = 0
        self.last_record_monotonic: float = 0.0

    def record_sample(
        self,
        t_frame_recv: float,
        t_frame_decoded: float,
        t_rcreader_update: float,
        t_manual_ctrl: float,
        t_mixer: float,
        t_motor_ctrl: float,
        t_pca_write: float,
    ) -> None:
        """Record a completed end-to-end pipeline sample with monotonic timestamps."""
        dec_lat = max(0.0, (t_frame_decoded - t_frame_recv) * 1000.0)
        rc_lat = max(0.0, (t_rcreader_update - t_frame_decoded) * 1000.0)
        mc_lat = max(0.0, (t_manual_ctrl - t_rcreader_update) * 1000.0)
        mix_lat = max(0.0, (t_mixer - t_manual_ctrl) * 1000.0)
        mot_lat = max(0.0, (t_motor_ctrl - t_mixer) * 1000.0)
        pca_lat = max(0.0, (t_pca_write - t_motor_ctrl) * 1000.0)
        total_lat = max(0.0, (t_pca_write - t_frame_recv) * 1000.0)

        with self._lock:
            self.decoder_latency_ms.append(dec_lat)
            self.rcreader_latency_ms.append(rc_lat)
            self.manual_ctrl_latency_ms.append(mc_lat)
            self.mixer_latency_ms.append(mix_lat)
            self.motor_ctrl_latency_ms.append(mot_lat)
            self.pca9685_write_latency_ms.append(pca_lat)
            self.total_pipeline_latency_ms.append(total_lat)

            self.sample_count += 1
            self.last_record_monotonic = t_pca_write

    @staticmethod
    def _calc_stats(data: List[float]) -> Dict[str, float]:
        """Calculates Min, Mean, P50, P95, P99, Max for a list of floats."""
        if not data:
            return {"min": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

        s = sorted(data)
        n = len(s)
        p50_idx = int(0.50 * (n - 1))
        p95_idx = int(0.95 * (n - 1))
        p99_idx = int(0.99 * (n - 1))

        return {
            "min": round(s[0], 3),
            "mean": round(sum(s) / n, 3),
            "p50": round(s[p50_idx], 3),
            "p95": round(s[p95_idx], 3),
            "p99": round(s[p99_idx], 3),
            "max": round(s[-1], 3),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Thread-safe snapshot of percentiles and summary metrics across all stages."""
        with self._lock:
            count = self.sample_count
            dec_list = list(self.decoder_latency_ms)
            rc_list = list(self.rcreader_latency_ms)
            mc_list = list(self.manual_ctrl_latency_ms)
            mix_list = list(self.mixer_latency_ms)
            mot_list = list(self.motor_ctrl_latency_ms)
            pca_list = list(self.pca9685_write_latency_ms)
            tot_list = list(self.total_pipeline_latency_ms)

        return {
            "total_samples": count,
            "window_samples": len(tot_list),
            "stages_ms": {
                "decoder": self._calc_stats(dec_list),
                "rcreader": self._calc_stats(rc_list),
                "manual_controller": self._calc_stats(mc_list),
                "mixer": self._calc_stats(mix_list),
                "motor_controller": self._calc_stats(mot_list),
                "pca9685_write": self._calc_stats(pca_list),
                "total_pipeline": self._calc_stats(tot_list),
            },
        }

    def reset(self) -> None:
        """Reset all statistical buffers."""
        with self._lock:
            self.decoder_latency_ms.clear()
            self.rcreader_latency_ms.clear()
            self.manual_ctrl_latency_ms.clear()
            self.mixer_latency_ms.clear()
            self.motor_ctrl_latency_ms.clear()
            self.pca9685_write_latency_ms.clear()
            self.total_pipeline_latency_ms.clear()
            self.sample_count = 0


# Global singleton tracker instance
latency_tracker = LatencyTracker()
