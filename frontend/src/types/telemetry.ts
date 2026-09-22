export type OperatingMode = 'manual' | 'semi_autonomous';

export interface GPSData {
  connected: boolean;
  fix_valid: boolean;
  fix_quality: number;         // 0=Invalid, 1=GPS, 2=DGPS, etc.
  fix_type: 'none' | '2D' | '3D';
  
  latitude: number | null;
  longitude: number | null;
  altitude_m: number | null;
  
  speed_knots: number | null;
  speed_mps: number | null;
  course_deg: number | null;
  
  satellites_used: number;     // Active fix solution count (GGA/GSA)
  satellites_visible: number;  // Tracked satellites in view (GSV)
  active_prns: string[];
  
  hdop: number | null;
  pdop: number | null;
  vdop: number | null;
  
  timestamp_utc: string | null;
  last_update_monotonic: number;
  data_age_seconds: number;
  is_stale: boolean;
  
  source: string;
  raw_sample: string | null;
  sentence_counts: Record<string, number>;

  // Persistence and source state
  position_source: 'live' | 'last_known' | 'none';
  live_fix_valid: boolean;
  awaiting_live_fix: boolean;
  last_known_fix_age_seconds: number | null;
  last_known_timestamp_iso: string | null;
}

export interface FilterDiagnostics {
  filter_mode: 'init' | 'stationary' | 'moving' | 'coasting' | 'outage' | 'recovery' | 'disabled';
  innovation_distance_m: number | null;
  rejected_count: number;
  accepted_count: number;
  reseed_count: number;
  last_reseed_reason: string | null;
  gnss_age_seconds: number;
  displacement_m: number | null;
}

export interface FilteredPosition {
  latitude: number | null;
  longitude: number | null;
  speed_mps: number | null;
  course_deg: number | null;
  is_filtered: boolean;
  uncertainty_warning: boolean;
  diagnostics: FilterDiagnostics;
}

export interface SystemHealth {
  cpu_temp_c: number | null;
  throttled_hex: string | null;
  throttled_description: string;
  memory_used_mb: number | null;
  memory_total_mb: number | null;
  uptime_seconds: number;
  lte_connected: boolean;
  lte_ip: string | null;
}

export interface IMUVector3 {
  x: number;
  y: number;
  z: number;
  unit: string;
}

export interface IMUCalibrationStatus {
  sys: number;
  gyro: number;
  accel: number;
  mag: number;
}

export interface IMUOrientation {
  roll: number;
  pitch: number;
  yaw: number;
  magnetic_heading_deg: number;
  true_heading_deg: number;
  heading_valid: boolean;
}

export interface IMUBodyAxis {
  forward_axis: string;
  lateral_axis: string;
  vertical_axis: string;
  coordinate_frame: string;
}

export interface IMUData {
  connected: boolean;
  calibrated: boolean;
  lifecycle_state: 'uninitialized' | 'calibrating' | 'ready' | 'stale' | 'disconnected';
  is_stale: boolean;
  data_age_seconds: number;
  timestamp_utc: string | null;
  last_update_monotonic: number;
  calibration: IMUCalibrationStatus;
  acceleration: IMUVector3;
  raw_acceleration: IMUVector3;
  gravity: IMUVector3;
  gyroscope: IMUVector3;
  orientation: IMUOrientation;
  body_axis: IMUBodyAxis;
  temperature_c?: number | null;
}

export interface SafetyStatus {
  ir_sensor_connected: boolean;
  ir_obstacle_detected: boolean;
  ir_gpio_level: number;
  ir_last_change_timestamp: string | null;
  obstacle_estop_active: boolean;
  obstacle_estop_reason: string | null;
  obstacle_estop_latched: boolean;
  reset_allowed: boolean;
  detection_range_status: string;
}

export interface RCStatus {
  rc_enabled: boolean;
  protocol: string;
  connected: boolean;
  signal_health: 'HEALTHY' | 'LOST' | 'DISCONNECTED';
  failsafe_active: boolean;
  data_age_seconds: number;
  last_frame_monotonic: number;
  ch1_raw: number | null;
  ch3_raw: number | null;
  ch5_raw: number | null;
  normalized_steering: number;
  normalized_throttle: number;
  manual_requested: boolean;
  total_frames: number;
  valid_frames: number;
  rejected_frames: number;
  glitch_count: number;
}

export interface ManualControlStatus {
  state: 'DISCONNECTED' | 'STANDBY' | 'ACTIVE' | 'FAILSAFE' | 'LOCKED_OUT';
  is_active: boolean;
  control_available: boolean;
  throttle_zero_confirmed: boolean;
  lockout_reason?: string | null;
  motors_inhibited: boolean;
}

export interface MotorStatus {
  left_output: number;
  right_output: number;
  left_pwm_us: number;
  right_pwm_us: number;
  left_percent: number;
  right_percent: number;
  neutralized: boolean;
  motors_enabled: boolean;
  safety_override_active: boolean;
  requested_throttle?: number | null;
  requested_steering?: number | null;
}

export interface ASVTelemetry {
  timestamp_iso: string;
  operating_mode: OperatingMode;
  gps: GPSData;
  filtered: FilteredPosition;
  imu: IMUData;
  system: SystemHealth;
  safety: SafetyStatus;
  rc?: RCStatus;
  manual_control?: ManualControlStatus;
  motors?: MotorStatus;
}

