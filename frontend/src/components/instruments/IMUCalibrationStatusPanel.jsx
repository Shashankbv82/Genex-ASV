import React from 'react';
import { CheckCircle2, AlertTriangle, ShieldCheck, Clock, Cpu, AlertOctagon } from 'lucide-react';
import { formatNumber, formatAge } from '../../utils/formatters';

/**
 * IMUCalibrationStatusPanel - BNO055 Calibration & Health Diagnostics
 * Displays 4-segment discrete calibration meters (Sys, Gyro, Accel, Mag 0-3),
 * sensor lifecycle badge, latency tracking with color thresholds, and hardware metadata.
 */
export function IMUCalibrationStatusPanel({ imu }) {
  const isConnected = Boolean(imu?.connected);
  const isStale = Boolean(imu?.is_stale);
  const lifecycle = imu?.lifecycle_state || 'disconnected';
  const ageSec = typeof imu?.data_age_seconds === 'number' ? imu.data_age_seconds : 999;

  const calib = imu?.calibration || { sys: 0, gyro: 0, accel: 0, mag: 0 };

  // Latency styling
  let latencyColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
  let latencyLabel = 'OPTIMAL';
  if (!isConnected || ageSec > 1.0) {
    latencyColor = 'text-red-400 bg-red-500/10 border-red-500/30';
    latencyLabel = 'HIGH / LOST';
  } else if (ageSec > 0.2) {
    latencyColor = 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    latencyLabel = 'MODERATE';
  }

  // Lifecycle badge style
  const getLifecycleBadge = () => {
    switch (lifecycle) {
      case 'ready':
        return {
          label: 'OPERATIONAL / READY',
          cls: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
          icon: ShieldCheck,
        };
      case 'calibrating':
        return {
          label: 'CALIBRATING',
          cls: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
          icon: AlertTriangle,
        };
      case 'stale':
        return {
          label: 'DATA STALE',
          cls: 'bg-red-500/20 text-red-300 border-red-500/40',
          icon: AlertOctagon,
        };
      default:
        return {
          label: 'DISCONNECTED',
          cls: 'bg-slate-800 text-slate-400 border-slate-700',
          icon: AlertOctagon,
        };
    }
  };

  const badge = getLifecycleBadge();
  const BadgeIcon = badge.icon;

  // Discrete 3-segment calibration meter
  const CalibMeter = ({ label, value, note }) => {
    const val = typeof value === 'number' ? Math.max(0, Math.min(3, value)) : 0;

    return (
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
            {label}
          </span>
          <span className="font-mono text-xs font-bold text-slate-100">
            {isConnected ? `${val}/3` : '0/3'}
          </span>
        </div>

        {/* 3-Segment Visual Bar */}
        <div className="grid grid-cols-3 gap-1.5 h-2.5 mb-2">
          {[1, 2, 3].map((seg) => {
            const isFilled = isConnected && val >= seg;
            let segColor = 'bg-slate-800';
            if (isFilled) {
              if (val === 3) segColor = 'bg-emerald-400 shadow-sm shadow-emerald-400/50';
              else if (val === 2) segColor = 'bg-amber-400 shadow-sm shadow-amber-400/50';
              else segColor = 'bg-amber-500';
            }
            return (
              <div
                key={`seg-${seg}`}
                className={`rounded-sm transition-all duration-200 ${segColor}`}
              />
            );
          })}
        </div>

        <span className="text-[10px] text-slate-400 font-mono">
          {isConnected ? (val === 3 ? 'Full Precision' : val > 0 ? 'Partial Calib' : 'Uncalibrated') : 'Offline'}
        </span>
      </div>
    );
  };

  return (
    <div className="bg-[#0B1220] border border-slate-800/90 rounded-2xl p-4 shadow-xl flex flex-col relative overflow-hidden">
      {/* Header Bar */}
      <div className="w-full flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Sensor Health & Calibration
          </span>
        </div>

        {/* Lifecycle Badge */}
        <div className={`flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full border ${badge.cls}`}>
          <BadgeIcon className="w-3 h-3" />
          <span>{badge.label}</span>
        </div>
      </div>

      {/* Stale Data Warning Banner */}
      {isStale && (
        <div className="mb-3 bg-red-950/40 border border-red-800/60 rounded-xl p-2.5 flex items-center gap-2 text-red-300">
          <AlertOctagon className="w-4 h-4 text-red-400 flex-shrink-0" />
          <div className="text-xs">
            <strong className="block font-semibold">Sensor Telemetry Stale (&gt;1.0s)</strong>
            <span className="text-red-400/80 text-[10px]">
              IMU reader loop is not producing fresh updates. Check physical I2C wiring.
            </span>
          </div>
        </div>
      )}

      {/* 4-Segment Calibration Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-3">
        <CalibMeter label="System" value={calib.sys} />
        <CalibMeter label="Gyroscope" value={calib.gyro} />
        <CalibMeter label="Accelerometer" value={calib.accel} />
        <CalibMeter label="Magnetometer" value={calib.mag} />
      </div>

      {/* Latency and Hardware Metadata Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
        {/* Latency Stat */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[10px]">Data Age</span>
          </div>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${latencyColor}`}>
            {isConnected ? formatAge(ageSec) : 'Offline'}
          </span>
        </div>

        {/* Bus Address */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 flex items-center justify-between">
          <span className="text-[10px] text-slate-400">I²C Interface</span>
          <span className="font-bold text-slate-200">/dev/i2c-1 (0x28)</span>
        </div>

        {/* Sampling Rates */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 flex items-center justify-between">
          <span className="text-[10px] text-slate-400">Sample / Telem</span>
          <span className="font-bold text-slate-200">20 Hz / 5 Hz</span>
        </div>
      </div>
    </div>
  );
}
