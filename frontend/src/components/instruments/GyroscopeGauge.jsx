import React, { useState } from 'react';
import { RotateCcw, ArrowLeftRight, Navigation } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

/**
 * GyroscopeGauge - 3-Axis Angular Velocity & Marine Rate of Turn (ROT)
 * Visualizes Roll Rate (omega_X), Pitch Rate (omega_Y), and Yaw Rate (omega_Z)
 * in both rad/s and deg/s with a marine-standard Rate of Turn bar.
 */
export function GyroscopeGauge({ imu }) {
  const isConnected = Boolean(imu?.connected);
  const [unitMode, setUnitMode] = useState('degs'); // 'degs' | 'rads'

  const gyro = imu?.gyroscope || { x: 0, y: 0, z: 0 };

  // Radian to Degree factor
  const RAD_TO_DEG = 180 / Math.PI;

  // Convert angular rates
  const getRate = (val) => {
    const v = typeof val === 'number' && !isNaN(val) ? val : 0;
    return unitMode === 'degs' ? v * RAD_TO_DEG : v;
  };

  const omegaX = getRate(gyro.x);
  const omegaY = getRate(gyro.y);
  const omegaZ = getRate(gyro.z); // Yaw Rate / ROT

  // Dedicated ROT in deg/s for standard marine scale
  const rotDegS = typeof gyro.z === 'number' && !isNaN(gyro.z) ? gyro.z * RAD_TO_DEG : 0;

  // ROT Scale max: 30 deg/s
  const ROT_MAX = 30.0;
  const rotPct = Math.min(Math.abs(rotDegS) / ROT_MAX, 1.0) * 50;
  const isStarboard = rotDegS >= 0;

  // Angular rate row
  const RateRow = ({ label, axis, radVal, degVal, desc }) => {
    const activeVal = unitMode === 'degs' ? degVal : radVal;
    const unitStr = unitMode === 'degs' ? '°/s' : 'rad/s';

    return (
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold text-cyan-400 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
            {axis}
          </span>
          <div>
            <span className="text-xs font-semibold text-slate-200 block leading-tight">{label}</span>
            <span className="text-[10px] text-slate-400 font-mono">({desc})</span>
          </div>
        </div>

        <div className="text-right font-mono">
          <div className="text-sm font-bold text-slate-100 flex items-baseline justify-end gap-1">
            {isConnected ? formatNumber(activeVal, unitMode === 'degs' ? 2 : 4) : '--'}
            <span className="text-[10px] text-slate-400 font-normal">{unitStr}</span>
          </div>
          <span className="text-[9px] text-slate-500 block">
            {isConnected ? (unitMode === 'degs' ? `${formatNumber(radVal, 3)} rad/s` : `${formatNumber(degVal, 1)}°/s`) : ''}
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-[#0B1220] border border-slate-800/90 rounded-2xl p-4 shadow-xl flex flex-col relative overflow-hidden">
      {/* Header Bar */}
      <div className="w-full flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <RotateCcw className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Gyroscope & Rate of Turn
          </span>
        </div>

        {/* Unit Toggle */}
        <div className="flex items-center bg-slate-900/80 border border-slate-800 rounded-lg p-0.5 text-[10px] font-mono">
          <button
            type="button"
            onClick={() => setUnitMode('degs')}
            className={`px-2 py-0.5 rounded ${
              unitMode === 'degs' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            °/s (DEG)
          </button>
          <button
            type="button"
            onClick={() => setUnitMode('rads')}
            className={`px-2 py-0.5 rounded ${
              unitMode === 'rads' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            rad/s
          </button>
        </div>
      </div>

      {/* Marine Rate of Turn (ROT) Indicator Card */}
      <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 mb-3">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-200 uppercase tracking-wide">
              Rate of Turn (ROT)
            </span>
            <span
              className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded ${
                Math.abs(rotDegS) > 1.0
                  ? isStarboard
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    : 'bg-red-500/20 text-red-400 border border-red-500/40'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              {isConnected
                ? Math.abs(rotDegS) > 1.0
                  ? isStarboard ? 'STARBOARD' : 'PORT'
                  : 'STEADY'
                : '--'}
            </span>
          </div>

          <div className="font-mono text-xs font-bold text-cyan-300">
            {isConnected ? `${formatNumber(rotDegS, 1)}°/s` : '--'}
          </div>
        </div>

        {/* Marine ROT Horizontal Bar */}
        <div className="relative w-full h-3.5 bg-slate-900 rounded-full overflow-hidden border border-slate-800 flex items-center">
          {/* Zero Center Tick */}
          <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-slate-400 z-10" />

          {/* Port Turn Bar (Left / Red) */}
          {!isStarboard && isConnected && (
            <div
              className="absolute top-0 bottom-0 right-1/2 bg-red-500 rounded-l-full transition-all duration-100 shadow-sm shadow-red-500/50"
              style={{ width: `${rotPct}%` }}
            />
          )}

          {/* Starboard Turn Bar (Right / Green) */}
          {isStarboard && isConnected && (
            <div
              className="absolute top-0 bottom-0 left-1/2 bg-emerald-400 rounded-r-full transition-all duration-100 shadow-sm shadow-emerald-500/50"
              style={{ width: `${rotPct}%` }}
            />
          )}
        </div>

        {/* ROT Scale markers */}
        <div className="flex justify-between text-[9px] font-mono text-slate-400 mt-1">
          <span className="text-red-400 font-bold">PORT -30°/s</span>
          <span>-15°</span>
          <span className="text-slate-200">0</span>
          <span>+15°</span>
          <span className="text-emerald-400 font-bold">STBD +30°/s</span>
        </div>
      </div>

      {/* 3-Axis Angular Velocity Rows */}
      <div className="space-y-2 flex-1">
        <RateRow
          label="Roll Rate (ω_X)"
          axis="ω_X"
          radVal={gyro.x}
          degVal={gyro.x * RAD_TO_DEG}
          desc="Longitudinal / Banking"
        />
        <RateRow
          label="Pitch Rate (ω_Y)"
          axis="ω_Y"
          radVal={gyro.y}
          degVal={gyro.y * RAD_TO_DEG}
          desc="Transverse / Pitching"
        />
        <RateRow
          label="Yaw Rate (ω_Z)"
          axis="ω_Z"
          radVal={gyro.z}
          degVal={gyro.z * RAD_TO_DEG}
          desc="Vertical / Rate of Turn"
        />
      </div>

      {/* Subsystem attribution footer */}
      <div className="w-full mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400 font-mono text-[10px]">
        <span>Sensor: <strong>BNO055 Gyro</strong></span>
        <span>Filter: <strong>NDOF 20 Hz</strong></span>
      </div>
    </div>
  );
}
