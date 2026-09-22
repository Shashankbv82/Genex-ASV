import { useState, useEffect } from 'react';
import { telemetryWS } from '../services/websocket';
import { getTelemetry } from '../services/api';

const DEFAULT_TELEMETRY = {
  timestamp_iso: new Date().toISOString(),
  operating_mode: 'manual',
  gps: {
    connected: false,
    fix_valid: false,
    fix_quality: 0,
    fix_type: 'none',
    latitude: null,
    longitude: null,
    altitude_m: null,
    speed_knots: null,
    speed_mps: null,
    course_deg: null,
    satellites_used: 0,
    satellites_visible: 0,
    active_prns: [],
    hdop: null,
    pdop: null,
    vdop: null,
    timestamp_utc: null,
    last_update_monotonic: 0.0,
    data_age_seconds: 999.0,
    is_stale: true,
    source: 'SIMCom A7672S UART (/dev/ttyS0)',
    raw_sample: null,
    sentence_counts: {}
  },
  filtered: {
    latitude: null,
    longitude: null,
    speed_mps: null,
    course_deg: null,
    is_filtered: false,
    uncertainty_warning: false,
    diagnostics: {
      filter_mode: 'disabled',
      innovation_distance_m: null,
      rejected_count: 0,
      accepted_count: 0,
      reseed_count: 0,
      last_reseed_reason: null,
      gnss_age_seconds: 0.0,
      displacement_m: null
    }
  },
  imu: {
    connected: false,
    calibrated: false,
    lifecycle_state: 'uninitialized',
    is_stale: true,
    data_age_seconds: 999.0,
    timestamp_utc: null,
    last_update_monotonic: 0.0,
    calibration: { sys: 0, gyro: 0, accel: 0, mag: 0 },
    acceleration: { x: 0.0, y: 0.0, z: 0.0, unit: 'm/s²' },
    raw_acceleration: { x: 0.0, y: 0.0, z: 0.0, unit: 'm/s²' },
    gravity: { x: 0.0, y: 0.0, z: 0.0, unit: 'm/s²' },
    gyroscope: { x: 0.0, y: 0.0, z: 0.0, unit: 'rad/s' },
    orientation: {
      roll: 0.0,
      pitch: 0.0,
      yaw: 0.0,
      magnetic_heading_deg: 0.0,
      true_heading_deg: 0.0,
      heading_valid: false
    },
    body_axis: {
      forward_axis: '+X',
      lateral_axis: '+Y',
      vertical_axis: '+Z',
      coordinate_frame: 'FRD'
    },
    temperature_c: null
  },
  system: {
    cpu_temp_c: null,
    throttled_hex: null,
    throttled_description: 'Normal',
    memory_used_mb: null,
    memory_total_mb: null,
    uptime_seconds: 0,
    lte_connected: false,
    lte_ip: null
  },
  safety: {
    ir_sensor_connected: false,
    ir_obstacle_detected: false,
    ir_gpio_level: 1,
    ir_last_change_timestamp: null,
    obstacle_estop_active: false,
    obstacle_estop_reason: null,
    obstacle_estop_latched: false,
    reset_allowed: true,
    detection_range_status: 'Proximity threshold only (potentiometer adjusted)'
  },
  rc: {
    rc_enabled: true,
    protocol: 'PPM',
    connected: false,
    signal_health: 'DISCONNECTED',
    failsafe_active: true,
    data_age_seconds: 999.0,
    ch1_raw: null,
    ch3_raw: null,
    ch5_raw: null,
    normalized_steering: 0.0,
    normalized_throttle: 0.0,
    manual_requested: false,
    total_frames: 0,
    valid_frames: 0,
    rejected_frames: 0,
    glitch_count: 0
  },
  manual_control: {
    state: 'DISCONNECTED',
    is_active: false,
    control_available: false,
    throttle_zero_confirmed: false,
    lockout_reason: 'STARTING',
    motors_inhibited: true
  },
  motors: {
    left_output: 0.0,
    right_output: 0.0,
    left_pwm_us: 1500.0,
    right_pwm_us: 1500.0,
    left_percent: 0.0,
    right_percent: 0.0,
    neutralized: true,
    motors_enabled: false,
    safety_override_active: false,
    requested_throttle: null,
    requested_steering: null
  }
};

export function useTelemetry() {
  const [telemetry, setTelemetry] = useState(DEFAULT_TELEMETRY);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    let mounted = true;

    const mergeTelemetry = (prev, data) => ({
      ...prev,
      ...data,
      gps: { ...prev.gps, ...(data.gps || {}) },
      filtered: {
        ...prev.filtered,
        ...(data.filtered || {}),
        diagnostics: {
          ...prev.filtered.diagnostics,
          ...((data.filtered && data.filtered.diagnostics) || {})
        }
      },
      imu: {
        ...prev.imu,
        ...(data.imu || {}),
        calibration: {
          ...prev.imu.calibration,
          ...((data.imu && data.imu.calibration) || {})
        },
        acceleration: {
          ...prev.imu.acceleration,
          ...((data.imu && data.imu.acceleration) || {})
        },
        raw_acceleration: {
          ...prev.imu.raw_acceleration,
          ...((data.imu && data.imu.raw_acceleration) || {})
        },
        gravity: {
          ...prev.imu.gravity,
          ...((data.imu && data.imu.gravity) || {})
        },
        gyroscope: {
          ...prev.imu.gyroscope,
          ...((data.imu && data.imu.gyroscope) || {})
        },
        orientation: {
          ...prev.imu.orientation,
          ...((data.imu && data.imu.orientation) || {})
        },
        body_axis: {
          ...prev.imu.body_axis,
          ...((data.imu && data.imu.body_axis) || {})
        }
      },
      system: { ...prev.system, ...(data.system || {}) },
      safety: { ...prev.safety, ...(data.safety || {}) },
      rc: { ...prev.rc, ...(data.rc || {}) },
      manual_control: { ...prev.manual_control, ...(data.manual_control || {}) },
      motors: { ...prev.motors, ...(data.motors || {}) }
    });

    // Initial fetch via REST
    getTelemetry()
      .then(data => {
        if (mounted && data && typeof data === 'object') {
          setTelemetry(prev => mergeTelemetry(prev, data));
        }
      })
      .catch(err => {
        console.warn('Initial REST telemetry fetch skipped/failed:', err?.message || err);
      });

    // Connect WebSocket
    telemetryWS.connect();

    const unsubData = telemetryWS.subscribe((data) => {
      if (mounted && data && typeof data === 'object') {
        setTelemetry(prev => mergeTelemetry(prev, data));
      }
    });


    const unsubStatus = telemetryWS.subscribeStatus((connected) => {
      if (mounted) {
        setWsConnected(connected);
      }
    });

    return () => {
      mounted = false;
      unsubData();
      unsubStatus();
    };
  }, []);

  return { telemetry, wsConnected };
}
