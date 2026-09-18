"""
GENEX ASV - Telemetry and Normalized GPS State Model
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import time
from datetime import datetime, timezone

class GPSData(BaseModel):
    connected: bool = False
    fix_valid: bool = False
    fix_quality: int = 0         # 0=Invalid, 1=GPS, 2=DGPS, etc.
    fix_type: str = "none"       # none, 2D, 3D
    
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    
    speed_knots: Optional[float] = None
    speed_mps: Optional[float] = None
    course_deg: Optional[float] = None
    
    satellites_used: int = 0     # Count used in active fix solution (GGA/GSA)
    satellites_visible: int = 0  # Total satellites tracked in view (GSV)
    active_prns: List[str] = Field(default_factory=list)
    
    hdop: Optional[float] = None
    pdop: Optional[float] = None
    vdop: Optional[float] = None
    
    timestamp_utc: Optional[str] = None
    last_update_monotonic: float = 0.0
    data_age_seconds: float = 999.0
    is_stale: bool = True
    
    source: str = "SIMCom A7672S UART (/dev/ttyS0)"
    raw_sample: Optional[str] = None
    sentence_counts: Dict[str, int] = Field(default_factory=dict)

class FilterDiagnostics(BaseModel):
    filter_mode: str = "disabled"  # init | stationary | moving | coasting | outage | recovery | disabled
    innovation_distance_m: Optional[float] = None
    rejected_count: int = 0
    accepted_count: int = 0
    reseed_count: int = 0
    last_reseed_reason: Optional[str] = None
    gnss_age_seconds: float = 0.0
    displacement_m: Optional[float] = None

class FilteredPosition(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_mps: Optional[float] = None
    course_deg: Optional[float] = None
    is_filtered: bool = False
    uncertainty_warning: bool = False
    diagnostics: FilterDiagnostics = Field(default_factory=FilterDiagnostics)

class SystemHealth(BaseModel):
    cpu_temp_c: Optional[float] = None
    throttled_hex: Optional[str] = None
    throttled_description: str = "Normal"
    memory_used_mb: Optional[float] = None
    memory_total_mb: Optional[float] = None
    uptime_seconds: float = 0.0
    lte_connected: bool = False
    lte_ip: Optional[str] = None

class IMUVector3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    unit: str = "m/s²"

class IMUCalibrationStatus(BaseModel):
    sys: int = 0
    gyro: int = 0
    accel: int = 0
    mag: int = 0

class IMUOrientation(BaseModel):
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    magnetic_heading_deg: float = 0.0
    true_heading_deg: float = 0.0
    heading_valid: bool = False

class IMUBodyAxis(BaseModel):
    forward_axis: str = "+X"
    lateral_axis: str = "+Y"
    vertical_axis: str = "+Z"
    coordinate_frame: str = "FRD"

class IMUData(BaseModel):
    connected: bool = False
    calibrated: bool = False
    lifecycle_state: str = "uninitialized"  # uninitialized | calibrating | ready | stale | disconnected
    is_stale: bool = True
    data_age_seconds: float = 999.0
    timestamp_utc: Optional[str] = None
    last_update_monotonic: float = 0.0

    calibration: IMUCalibrationStatus = Field(default_factory=IMUCalibrationStatus)
    acceleration: IMUVector3 = Field(default_factory=lambda: IMUVector3(unit="m/s²"))
    raw_acceleration: IMUVector3 = Field(default_factory=lambda: IMUVector3(unit="m/s²"))
    gravity: IMUVector3 = Field(default_factory=lambda: IMUVector3(unit="m/s²"))
    gyroscope: IMUVector3 = Field(default_factory=lambda: IMUVector3(unit="rad/s"))
    orientation: IMUOrientation = Field(default_factory=IMUOrientation)
    body_axis: IMUBodyAxis = Field(default_factory=IMUBodyAxis)
    temperature_c: Optional[float] = None

class ASVTelemetry(BaseModel):
    timestamp_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operating_mode: str = "manual"  # manual | semi_autonomous
    gps: GPSData = Field(default_factory=GPSData)
    filtered: FilteredPosition = Field(default_factory=FilteredPosition)
    imu: IMUData = Field(default_factory=IMUData)
    system: SystemHealth = Field(default_factory=SystemHealth)

