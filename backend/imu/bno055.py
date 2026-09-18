"""
GENEX ASV - BNO055 9-DOF Absolute Orientation Sensor Driver
Pure Python I2C register driver with clock-stretching retry resilience.
"""

import os
import fcntl
import time
import struct
import math
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger("genex.imu.bno055")

I2C_SLAVE = 0x0703

# BNO055 Registers (Page 0)
REG_CHIP_ID = 0x00
REG_ACC_ID = 0x01
REG_MAG_ID = 0x02
REG_GYR_ID = 0x03
REG_SW_REV_ID_LSB = 0x04
REG_PAGE_ID = 0x07

# Data Registers
REG_ACC_DATA_X_LSB = 0x08
REG_MAG_DATA_X_LSB = 0x0E
REG_GYR_DATA_X_LSB = 0x14
REG_EUL_HEADING_LSB = 0x1A
REG_QUA_DATA_W_LSB = 0x20
REG_LIA_DATA_X_LSB = 0x28
REG_GRV_DATA_X_LSB = 0x2E
REG_TEMP = 0x34
REG_CALIB_STAT = 0x35

# Mode & Config Registers
REG_SYS_STATUS = 0x39
REG_SYS_ERR = 0x3A
REG_UNIT_SEL = 0x3B
REG_OPR_MODE = 0x3D
REG_PWR_MODE = 0x3E
REG_SYS_TRIGGER = 0x3F

# Operation Modes
MODE_CONFIG = 0x00
MODE_IMU = 0x08       # Accel + Gyro relative
MODE_COMPASS = 0x09   # Accel + Mag
MODE_M4G = 0x0A
MODE_NDOF_FMC_OFF = 0x0B
MODE_NDOF = 0x0C      # 9-DOF Absolute Fusion

BNO055_CHIP_ID_VALUE = 0xA0

@dataclass
class IMUSnapshot:
    connected: bool
    calibrated: bool
    sys_calib: int
    gyro_calib: int
    accel_calib: int
    mag_calib: int
    
    # Linear acceleration (m/s^2, gravity removed)
    lin_acc_x: float
    lin_acc_y: float
    lin_acc_z: float
    
    # Total acceleration (m/s^2, including gravity)
    raw_acc_x: float
    raw_acc_y: float
    raw_acc_z: float
    
    # Gravity vector (m/s^2)
    grav_x: float
    grav_y: float
    grav_z: float
    
    # Angular velocity (rad/s)
    gyro_x: float
    gyro_y: float
    gyro_z: float
    
    # Euler angles (deg)
    yaw_deg: float      # ASV forward heading (0 to 360)
    roll_deg: float     # roll (-180 to +180)
    pitch_deg: float    # pitch (-180 to +180)
    mag_heading_deg: float
    true_heading_deg: float
    heading_valid: bool
    
    temp_c: Optional[float] = None
    timestamp_mono: float = 0.0

class BNO055:
    def __init__(self, bus: int = 1, address: int = 0x28):
        self.bus_num = bus
        self.address = address
        self.bus_path = f"/dev/i2c-{bus}"
        self._fd: Optional[int] = None
        self._connected = False
        self.last_read_time = 0.0

    def open(self) -> bool:
        """Opens I2C bus device file."""
        if self._fd is not None:
            return True
        try:
            self._fd = os.open(self.bus_path, os.O_RDWR)
            fcntl.ioctl(self._fd, I2C_SLAVE, self.address)
            self._connected = True
            return True
        except Exception as e:
            logger.warning("Failed to open %s at 0x%02X: %s", self.bus_path, self.address, e)
            self._fd = None
            self._connected = False
            return False

    def close(self):
        """Closes I2C bus device."""
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
        self._connected = False

    def _read_bytes(self, reg: int, length: int) -> bytes:
        """Reads multiple bytes from register with clock-stretching retry logic."""
        if self._fd is None:
            raise OSError("I2C bus not open")

        last_err = None
        for attempt in range(3):
            try:
                os.write(self._fd, bytes([reg]))
                time.sleep(0.001)
                data = os.read(self._fd, length)
                if len(data) == length:
                    return data
            except (OSError, IOError) as e:
                last_err = e
                time.sleep(0.002)

        raise last_err or OSError(f"Read from 0x{reg:02X} timed out")

    def _write_byte(self, reg: int, value: int):
        """Writes single byte to register with retry logic."""
        if self._fd is None:
            raise OSError("I2C bus not open")

        last_err = None
        for attempt in range(3):
            try:
                os.write(self._fd, bytes([reg, value]))
                time.sleep(0.005)
                return
            except (OSError, IOError) as e:
                last_err = e
                time.sleep(0.005)

        raise last_err or OSError(f"Write to 0x{reg:02X} failed")

    def initialize(self) -> bool:
        """Executes BNO055 power-up and NDOF mode configuration sequence."""
        if not self.open():
            return False

        try:
            # 1. Switch to Page 0
            self._write_byte(REG_PAGE_ID, 0x00)
            time.sleep(0.01)

            # 2. Check Chip ID
            chip_id = self._read_bytes(REG_CHIP_ID, 1)[0]
            if chip_id != BNO055_CHIP_ID_VALUE:
                logger.error("BNO055 invalid Chip ID: 0x%02X (expected 0xA0)", chip_id)
                self.close()
                return False

            # 3. Enter CONFIGMODE
            self._write_byte(REG_OPR_MODE, MODE_CONFIG)
            time.sleep(0.03)

            # 4. Set Normal Power Mode
            self._write_byte(REG_PWR_MODE, 0x00)
            time.sleep(0.01)

            # 5. Set Unit Selection (m/s^2, dps, degrees, Windows orientation)
            self._write_byte(REG_UNIT_SEL, 0x00)
            time.sleep(0.01)

            # 6. Enter NDOF Mode
            self._write_byte(REG_OPR_MODE, MODE_NDOF)
            time.sleep(0.05)

            opr = self._read_bytes(REG_OPR_MODE, 1)[0]
            if (opr & 0x0F) != MODE_NDOF:
                logger.warning("BNO055 failed to enter NDOF mode: 0x%02X", opr)

            logger.info("BNO055 IMU initialized successfully in NDOF mode on %s (0x%02X)",
                        self.bus_path, self.address)
            self._connected = True
            return True
        except Exception as e:
            logger.error("Error during BNO055 initialization: %s", e)
            self.close()
            return False

    def read_telemetry(
        self,
        mounting_offset_deg: float = 0.0,
        declination_deg: float = 0.0
    ) -> Optional[IMUSnapshot]:
        """Reads complete inertial, attitude, and calibration snapshot."""
        if not self._connected or self._fd is None:
            if not self.initialize():
                return None

        try:
            t_now = time.monotonic()

            # Read Euler angles: Heading (yaw), Roll, Pitch (6 bytes: 0x1A-0x1F)
            e_bytes = self._read_bytes(REG_EUL_HEADING_LSB, 6)
            h_raw, r_raw, p_raw = struct.unpack("<hhh", e_bytes)
            raw_yaw = (h_raw / 16.0) % 360.0
            roll = round(r_raw / 16.0, 1)
            pitch = round(p_raw / 16.0, 1)

            # Read Linear Acceleration (gravity removed): 0x28-0x2D (6 bytes)
            l_bytes = self._read_bytes(REG_LIA_DATA_X_LSB, 6)
            lx_raw, ly_raw, lz_raw = struct.unpack("<hhh", l_bytes)
            lin_x = round(lx_raw / 100.0, 2)
            lin_y = round(ly_raw / 100.0, 2)
            lin_z = round(lz_raw / 100.0, 2)

            # Read Raw Acceleration (total with gravity): 0x08-0x0D (6 bytes)
            a_bytes = self._read_bytes(REG_ACC_DATA_X_LSB, 6)
            ax_raw, ay_raw, az_raw = struct.unpack("<hhh", a_bytes)
            raw_x = round(ax_raw / 100.0, 2)
            raw_y = round(ay_raw / 100.0, 2)
            raw_z = round(az_raw / 100.0, 2)

            # Read Gravity Vector: 0x2E-0x33 (6 bytes)
            g_bytes = self._read_bytes(REG_GRV_DATA_X_LSB, 6)
            gx_raw, gy_raw, gz_raw = struct.unpack("<hhh", g_bytes)
            grav_x = round(gx_raw / 100.0, 2)
            grav_y = round(gy_raw / 100.0, 2)
            grav_z = round(gz_raw / 100.0, 2)

            # Read Gyroscope angular rate: 0x14-0x19 (6 bytes)
            gyr_bytes = self._read_bytes(REG_GYR_DATA_X_LSB, 6)
            wx_raw, wy_raw, wz_raw = struct.unpack("<hhh", gyr_bytes)
            # 16 LSB per dps -> rad/s scale = (pi / 180.0) / 16.0
            scale_rad = (math.pi / 180.0) / 16.0
            gyro_x = round(wx_raw * scale_rad, 4)
            gyro_y = round(wy_raw * scale_rad, 4)
            gyro_z = round(wz_raw * scale_rad, 4)

            # Read Calibration status: 0x35 (1 byte)
            cal = self._read_bytes(REG_CALIB_STAT, 1)[0]
            sys_c = (cal >> 6) & 0x03
            gyro_c = (cal >> 4) & 0x03
            accel_c = (cal >> 2) & 0x03
            mag_c = cal & 0x03
            is_calibrated = (sys_c >= 2 and gyro_c >= 2)

            # Apply mounting offset and magnetic declination
            mag_heading = round((raw_yaw + mounting_offset_deg) % 360.0, 1)
            true_heading = round((mag_heading + declination_deg) % 360.0, 1)

            # Heading validity check (BNO055 heading is valid once gyro has calibrated)
            heading_valid = (gyro_c >= 1 or sys_c >= 1)

            self.last_read_time = t_now

            return IMUSnapshot(
                connected=True,
                calibrated=is_calibrated,
                sys_calib=sys_c,
                gyro_calib=gyro_c,
                accel_calib=accel_c,
                mag_calib=mag_c,
                lin_acc_x=lin_x,
                lin_acc_y=lin_y,
                lin_acc_z=lin_z,
                raw_acc_x=raw_x,
                raw_acc_y=raw_y,
                raw_acc_z=raw_z,
                grav_x=grav_x,
                grav_y=grav_y,
                grav_z=grav_z,
                gyro_x=gyro_x,
                gyro_y=gyro_y,
                gyro_z=gyro_z,
                yaw_deg=true_heading,
                roll_deg=roll,
                pitch_deg=pitch,
                mag_heading_deg=mag_heading,
                true_heading_deg=true_heading,
                heading_valid=heading_valid,
                timestamp_mono=t_now
            )
        except Exception as e:
            logger.warning("Error reading BNO055 telemetry: %s", e)
            self._connected = False
            self.close()
            return None
