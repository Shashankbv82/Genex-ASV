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
    SIMCOM_AT_PORT_CANDIDATES: list[str] = ["/dev/ttyUSB2", "/dev/ttyUSB1"]
    GPS_NMEA_SILENCE_TIMEOUT_SEC: float = 10.0
    GPS_RECOVERY_BACKOFF_BASE_SEC: float = 2.0
    GPS_RECOVERY_BACKOFF_MAX_SEC: float = 30.0

    # GPS Cache Persistence Settings
    GPS_CACHE_FILE: str = os.getenv("GENEX_GPS_CACHE_FILE", "data/last_gps_fix.json")
    GPS_CACHE_MIN_INTERVAL_SEC: float = 15.0
    GPS_CACHE_MIN_DISPLACEMENT_M: float = 2.0

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

    # IR Obstacle Sensor & Safety Settings
    ENABLE_IR_SENSOR: bool = os.getenv("GENEX_ENABLE_IR", "true").lower() == "true"
    IR_SENSOR_PIN: int = int(os.getenv("GENEX_IR_PIN", "17"))
    IR_ACTIVE_LOW: bool = os.getenv("GENEX_IR_ACTIVE_LOW", "true").lower() == "true"
    IR_DEBOUNCE_SEC: float = float(os.getenv("GENEX_IR_DEBOUNCE_SEC", "0.030"))

    # RC Receiver & FlySky Manual Mode Settings
    RC_ENABLED: bool = os.getenv("GENEX_RC_ENABLED", "true").lower() == "true"
    RC_PROTOCOL: str = os.getenv("GENEX_RC_PROTOCOL", "IBUS")  # "PPM" or "IBUS"
    RC_GPIO_PIN: int = int(os.getenv("GENEX_RC_GPIO_PIN", "22"))
    RC_SERIAL_PORT: str = os.getenv("GENEX_RC_SERIAL_PORT", "/dev/ttyUSB3")
    RC_SERIAL_BAUDRATE: int = int(os.getenv("GENEX_RC_SERIAL_BAUDRATE", "115200"))
    RC_LOOP_HZ: float = float(os.getenv("GENEX_RC_LOOP_HZ", "50.0"))
    RC_FAILSAFE_TIMEOUT_SEC: float = float(os.getenv("GENEX_RC_FAILSAFE_TIMEOUT", "1.0"))
    RC_SIGNAL_RESTORE_TIME_SEC: float = float(os.getenv("GENEX_RC_SIGNAL_RESTORE_TIME", "0.5"))
    RC_STEERING_CHANNEL: int = int(os.getenv("GENEX_RC_STEERING_CH", "1"))
    RC_THROTTLE_CHANNEL: int = int(os.getenv("GENEX_RC_THROTTLE_CH", "3"))
    RC_ARM_CHANNEL: int = int(os.getenv("GENEX_RC_ARM_CH", "5"))
    RC_MIN_US: int = int(os.getenv("GENEX_RC_MIN_US", "1000"))
    RC_NEUTRAL_US: int = int(os.getenv("GENEX_RC_NEUTRAL_US", "1500"))
    RC_MAX_US: int = int(os.getenv("GENEX_RC_MAX_US", "2000"))
    RC_DEADBAND_US: float = float(os.getenv("GENEX_RC_DEADBAND_US", "50.0"))
    RC_STEERING_DEADBAND_US: float = float(os.getenv("GENEX_RC_STEERING_DEADBAND_US", "50.0"))
    RC_EXPO_FACTOR: float = float(os.getenv("GENEX_RC_EXPO_FACTOR", "0.20"))
    RC_THROTTLE_ZERO_TOLERANCE_US: float = float(os.getenv("GENEX_RC_THROTTLE_ZERO_TOLERANCE_US", "50.0"))
    RC_ARM_WHEN_HIGH: bool = os.getenv("GENEX_RC_ARM_WHEN_HIGH", "true").lower() == "true"
    RC_ARM_THRESHOLD_US: int = int(os.getenv("GENEX_RC_ARM_THRESHOLD_US", "1500"))

    # Calibrated RC Channels
    RC_THROTTLE_MIN_US: int = int(os.getenv("GENEX_RC_THROTTLE_MIN_US", "1010"))
    RC_THROTTLE_MAX_US: int = int(os.getenv("GENEX_RC_THROTTLE_MAX_US", "2000"))
    RC_THROTTLE_DEADBAND_US: float = float(os.getenv("GENEX_RC_THROTTLE_DEADBAND_US", "15.0"))
    RC_STEERING_MIN_US: int = int(os.getenv("GENEX_RC_STEERING_MIN_US", "1050"))
    RC_STEERING_NEUTRAL_US: int = int(os.getenv("GENEX_RC_STEERING_NEUTRAL_US", "1500"))
    RC_STEERING_MAX_US: int = int(os.getenv("GENEX_RC_STEERING_MAX_US", "2025"))

    # Motor Controller & Differential Drive Mixer Settings
    MANUAL_THROTTLE_ACCEL_RATE: float = float(os.getenv("GENEX_MANUAL_THROTTLE_ACCEL", "0.50"))
    MANUAL_THROTTLE_DECEL_RATE: float = float(os.getenv("GENEX_MANUAL_THROTTLE_DECEL", "1.00"))
    MANUAL_STEERING_ACCEL_RATE: float = float(os.getenv("GENEX_MANUAL_STEERING_ACCEL", "1.50"))
    MANUAL_STEERING_DECEL_RATE: float = float(os.getenv("GENEX_MANUAL_STEERING_DECEL", "2.00"))
    RC_ACCELERATION_RATE: float = float(os.getenv("GENEX_RC_ACCEL_RATE", "0.50"))
    RC_DECELERATION_RATE: float = float(os.getenv("GENEX_RC_DECEL_RATE", "1.00"))
    MOTORS_ENABLED: bool = os.getenv("GENEX_MOTORS_ENABLED", "true").lower() == "true"
    LEFT_MOTOR_INVERT: float = float(os.getenv("GENEX_LEFT_MOTOR_INVERT", "1.0"))
    RIGHT_MOTOR_INVERT: float = float(os.getenv("GENEX_RIGHT_MOTOR_INVERT", "1.0"))
    PWM_NEUTRAL_US: float = float(os.getenv("GENEX_PWM_NEUTRAL_US", "1500.0"))
    PWM_MIN_US: float = float(os.getenv("GENEX_PWM_MIN_US", "1500.0"))
    PWM_MAX_US: float = float(os.getenv("GENEX_PWM_MAX_US", "2000.0"))

    # PCA9685 Hardware PWM Settings
    PCA9685_I2C_BUS: int = int(os.getenv("GENEX_PCA9685_BUS", "1"))
    PCA9685_I2C_ADDR: int = int(os.getenv("GENEX_PCA9685_ADDR", "0x40"), 16)
    PCA9685_PWM_FREQ_HZ: float = float(os.getenv("GENEX_PCA9685_FREQ", "50.0"))
    PCA9685_LEFT_CHANNEL: int = int(os.getenv("GENEX_PCA9685_LEFT_CH", "0"))
    PCA9685_RIGHT_CHANNEL: int = int(os.getenv("GENEX_PCA9685_RIGHT_CH", "1"))

settings = Settings()