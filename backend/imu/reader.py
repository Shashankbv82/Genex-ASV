"""
GENEX ASV - BNO055 Background Reader Thread
Samples IMU at 20 Hz, handles reconnection, lifecycle states, and thread-safe telemetry updates.
"""

import time
import threading
import logging
from typing import Optional
from datetime import datetime, timezone

from backend.config import settings
from backend.telemetry.state import (
    IMUData,
    IMUVector3,
    IMUCalibrationStatus,
    IMUOrientation,
    IMUBodyAxis
)
from backend.imu.bno055 import BNO055, IMUSnapshot

logger = logging.getLogger("genex.imu.reader")

class IMUReader:
    def __init__(self):
        self.driver = BNO055(bus=settings.IMU_I2C_BUS, address=settings.IMU_I2C_ADDR)
        self.poll_interval = 1.0 / settings.IMU_POLL_RATE_HZ
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        self._data = IMUData(
            connected=False,
            calibrated=False,
            lifecycle_state="uninitialized",
            is_stale=True,
            data_age_seconds=999.0,
            body_axis=IMUBodyAxis(
                forward_axis="+X",
                lateral_axis="+Y",
                vertical_axis="+Z",
                coordinate_frame=settings.IMU_COORDINATE_FRAME
            )
        )

    def start_reader(self):
        """Starts background IMU reader daemon thread."""
        if self.running:
            return
        if not settings.IMU_ENABLED:
            logger.info("IMU is disabled via configuration.")
            return

        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="IMUReaderThread")
        self._thread.start()
        logger.info("IMUReader thread started (polling @ %.1f Hz)", settings.IMU_POLL_RATE_HZ)

    def stop_reader(self):
        """Stops background IMU reader."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.driver.close()
        logger.info("IMUReader thread stopped.")

    def _run(self):
        reconnect_delay = 1.0
        while self.running:
            # 1. Attempt connection / initialization if not connected
            if not self.driver._connected:
                with self._lock:
                    self._data.connected = False
                    self._data.lifecycle_state = "disconnected"
                
                success = self.driver.initialize()
                if not success:
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, 5.0)
                    continue
                reconnect_delay = 1.0

            # 2. Read sensor telemetry snapshot
            snapshot = self.driver.read_telemetry(
                mounting_offset_deg=settings.IMU_MOUNTING_HEADING_OFFSET_DEG,
                declination_deg=settings.IMU_MAGNETIC_DECLINATION_DEG
            )

            now_mono = time.monotonic()
            now_utc = datetime.now(timezone.utc).isoformat()

            with self._lock:
                if snapshot is not None:
                    self._data.connected = True
                    self._data.calibrated = snapshot.calibrated
                    self._data.is_stale = False
                    self._data.last_update_monotonic = now_mono
                    self._data.data_age_seconds = 0.0
                    self._data.timestamp_utc = now_utc

                    # Determine lifecycle state
                    if snapshot.heading_valid and snapshot.calibrated:
                        self._data.lifecycle_state = "ready"
                    elif snapshot.heading_valid:
                        self._data.lifecycle_state = "ready"
                    else:
                        self._data.lifecycle_state = "calibrating"

                    # Update calibration
                    self._data.calibration = IMUCalibrationStatus(
                        sys=snapshot.sys_calib,
                        gyro=snapshot.gyro_calib,
                        accel=snapshot.accel_calib,
                        mag=snapshot.mag_calib
                    )

                    # Update linear acceleration (m/s^2, gravity compensated)
                    self._data.acceleration = IMUVector3(
                        x=snapshot.lin_acc_x,
                        y=snapshot.lin_acc_y,
                        z=snapshot.lin_acc_z,
                        unit="m/s²"
                    )

                    # Update raw acceleration (total with gravity)
                    self._data.raw_acceleration = IMUVector3(
                        x=snapshot.raw_acc_x,
                        y=snapshot.raw_acc_y,
                        z=snapshot.raw_acc_z,
                        unit="m/s²"
                    )

                    # Update gravity component
                    self._data.gravity = IMUVector3(
                        x=snapshot.grav_x,
                        y=snapshot.grav_y,
                        z=snapshot.grav_z,
                        unit="m/s²"
                    )

                    # Update angular velocity (rad/s)
                    self._data.gyroscope = IMUVector3(
                        x=snapshot.gyro_x,
                        y=snapshot.gyro_y,
                        z=snapshot.gyro_z,
                        unit="rad/s"
                    )

                    # Update orientation
                    self._data.orientation = IMUOrientation(
                        roll=snapshot.roll_deg,
                        pitch=snapshot.pitch_deg,
                        yaw=snapshot.yaw_deg,
                        magnetic_heading_deg=snapshot.mag_heading_deg,
                        true_heading_deg=snapshot.true_heading_deg,
                        heading_valid=snapshot.heading_valid
                    )

                    self._data.body_axis = IMUBodyAxis(
                        forward_axis="+X",
                        lateral_axis="+Y",
                        vertical_axis="+Z",
                        coordinate_frame=settings.IMU_COORDINATE_FRAME
                    )
                else:
                    self._data.connected = False
                    self._data.lifecycle_state = "disconnected"

            time.sleep(self.poll_interval)

    def get_state(self) -> IMUData:
        """Returns thread-safe snapshot of IMU data with updated data age."""
        with self._lock:
            now = time.monotonic()
            if self._data.last_update_monotonic > 0:
                age = round(now - self._data.last_update_monotonic, 2)
                self._data.data_age_seconds = age
                if age > settings.IMU_STALE_THRESHOLD_SEC:
                    self._data.is_stale = True
                    if self._data.lifecycle_state == "ready":
                        self._data.lifecycle_state = "stale"
                else:
                    self._data.is_stale = False
            else:
                self._data.data_age_seconds = 999.0
                self._data.is_stale = True


            return self._data.model_copy(deep=True)

# Singleton global instance
imu_reader = IMUReader()
