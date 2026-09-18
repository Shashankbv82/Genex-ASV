"""
GENEX ASV - Backend Configuration
"""

from pydantic import BaseModel
import os

class Settings(BaseModel):
    # Serial Port Settings
    GPS_SERIAL_PORT: str = os.getenv("GENEX_GPS_PORT", "/dev/ttyS0")
    GPS_BAUDRATE: int = int(os.getenv("GENEX_GPS_BAUD", "115200"))
    GPS_TIMEOUT: float = 1.0
    GPS_STALE_THRESHOLD_SEC: float = 3.0

    # API & WebSocket Server (0.0.0.0 = localhost + Tailscale/LAN; not public internet)
    API_HOST: str = os.getenv("GENEX_API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("GENEX_API_PORT", "8000"))
    TELEMETRY_BROADCAST_RATE_HZ: float = 5.0

    # Source identifier
    GPS_SOURCE_NAME: str = "SIMCom A7672S UART (/dev/ttyS0)"
    SIMCOM_AT_PORT: str = os.getenv("GENEX_AT_PORT", "/dev/ttyUSB2")

    # Adaptive Kalman Filter Settings
    ENABLE_GPS_FILTER: bool = os.getenv("GENEX_ENABLE_GPS_FILTER", "true").lower() == "true"
    GPS_FILTER_COURSE_MIN_SPEED: float = float(os.getenv("GENEX_FILTER_MIN_SPEED", "0.40"))
    GPS_FILTER_STATIONARY_ACCEL_SIGMA: float = 0.10
    GPS_FILTER_MOVING_ACCEL_SIGMA: float = 1.20
    GPS_FILTER_GATE_THRESHOLD: float = 9.21  # Chi-squared 2-DOF at p=0.01
    GPS_FILTER_MAX_COAST_SEC: float = 3.0
    GPS_FILTER_OUTAGE_CUTOFF_SEC: float = 3.0
    GPS_FILTER_RESEED_CLUSTER_SIZE: int = 3
    GPS_FILTER_RESEED_MAX_RADIUS_M: float = 2.5
    GPS_FILTER_MAX_ASV_SPEED_MPS: float = 3.5

    # IMU / BNO055 Settings
    IMU_ENABLED: bool = os.getenv("GENEX_ENABLE_IMU", "true").lower() == "true"
    IMU_I2C_BUS: int = int(os.getenv("GENEX_IMU_I2C_BUS", "1"))
    IMU_I2C_ADDR: int = int(os.getenv("GENEX_IMU_I2C_ADDR", "0x28"), 16)
    IMU_POLL_RATE_HZ: float = float(os.getenv("GENEX_IMU_POLL_RATE", "20.0"))
    IMU_STALE_THRESHOLD_SEC: float = 1.0
    IMU_MOUNTING_HEADING_OFFSET_DEG: float = float(os.getenv("GENEX_IMU_HEADING_OFFSET", "0.0"))
    IMU_MAGNETIC_DECLINATION_DEG: float = float(os.getenv("GENEX_IMU_DECLINATION", "-1.2"))
    IMU_COORDINATE_FRAME: str = os.getenv("GENEX_IMU_FRAME", "FRD")

settings = Settings()

