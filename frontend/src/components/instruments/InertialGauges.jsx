import React, { useState } from 'react';
import { Activity, Zap, Compass, ArrowRight } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

/**
 * InertialGauges - Tri-Component Accelerometer Visualizer
 * Visualizes Linear Acceleration (gravity removed), Raw Acceleration (total),
 * and Earth Gravity Vector across Surge (X), Sway (Y), and Heave (Z) axes
 * with bipolar zero-centered meters and vector magnitude.
 */
export function InertialGauges({ imu }) {
  const isConnected = Boolean(imu?.connected);
  const [activeTab, setActiveTab] = useState('linear'); // 'linear' | 'raw' | 'gravity'

  const linAcc = imu?.acceleration || { x: 0, y: 0, z: 0 };
  const rawAcc = imu?.raw_acceleration || { x: 0, y: 0, z: 0 };
  const grav = imu?.gravity || { x: 0, y: 0, z: 0 };

  // Select active vector
  const currentVector =
    activeTab === 'linear'
      ? linAcc
      : activeTab === 'raw'
      ? rawAcc
      : grav;

  const currentDesc =
    activeTab === 'linear'
      ? 'Dynamic vessel motion with Earth gravity mathematically subtracted'
      : activeTab === 'raw'
      ? 'Total combined inertial acceleration measured by sensor'
      : 'Earth static gravitational field decomposed onto vehicle body axes';

  // Magnitude: |a| = sqrt(x^2 + y^2 + z^2)
  const calcMag = (v) => Math.sqrt((v.x || 0) ** 2 + (v.y || 0) ** 2 + (v.z || 0) ** 2);
  const linMag = calcMag(linAcc);
  const rawMag = calcMag(rawAcc);
  const gravMag = calcMag(grav);
  const activeMag = calcMag(currentVector);

  // Maximum scale for bipolar bar
  const maxScale = activeTab === 'linear' ? 5.0 : 15.0;

  // Bipolar bar component
  const BipolarBar = ({ value, label, axisName, desc }) => {
    const val = typeof value === 'number' && !isNaN(value) ? value : 0;
    // Percent from center (0 to 50%)
    const pct = Math.min(Math.abs(val) / maxScale, 1.0) * 50;
    const isPositive = val >= 0;

    // Color based on magnitude and type
    let barColor = 'bg-cyan-400';
    if (activeTab === 'linear') {
      if (Math.abs(val) > 3.0) barColor = 'bg-red-400';
      else if (Math.abs(val) > 1.5) barColor = 'bg-amber-400';
      else barColor = 'bg-emerald-400';
    } else {
      barColor = 'bg-indigo-400';
    }

    return (
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
        {/* Row Header */}
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-cyan-400">{axisName}</span>
            <span className="text-xs font-semibold text-slate-200">{label}</span>
            <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">({desc})</span>
          </div>
          <div className="font-mono text-xs font-bold text-slate-100 flex items-baseline gap-1">
            {isConnected ? formatNumber(val, 2) : '--'}
            <span className="text-[10px] text-slate-400 font-normal">m/s²</span>
          </div>
        </div>

        {/* Bipolar Zero-Centered Bar Gauge */}
        <div className="relative w-full h-3 bg-slate-950 rounded-full overflow-hidden border border-slate-800 flex items-center">
          {/* Zero Center Divider Line */}
          <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-slate-600 z-10" />

          {/* Left / Negative Bar (from 50% down to 0%) */}
          {!isPositive && isConnected && (
            <div
              className={`absolute top-0 bottom-0 right-1/2 ${barColor} rounded-l-full transition-all duration-100`}
              style={{ width: `${pct}%` }}
            />
          )}

          {/* Right / Positive Bar (from 50% up to 100%) */}
          {isPositive && isConnected && (
            <div
              className={`absolute top-0 bottom-0 left-1/2 ${barColor} rounded-r-full transition-all duration-100`}
              style={{ width: `${pct}%` }}
            />
          )}
        </div>

        {/* Scale labels */}
        <div className="flex justify-between text-[9px] font-mono text-slate-400 mt-1">
          <span>-{maxScale}</span>
          <span>-{(maxScale / 2).toFixed(1)}</span>
          <span className="text-slate-200 font-bold">0.0</span>
          <span>+{(maxScale / 2).toFixed(1)}</span>
          <span>+{maxScale}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-[#0B1220] border border-slate-800/90 rounded-2xl p-4 shadow-xl flex flex-col relative overflow-hidden">
      {/* Header Bar */}
      <div className="w-full flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Inertial Acceleration
          </span>
          <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-1.5 py-0.5 rounded">
            3-AXIS
          </span>
        </div>

        {/* Magnitude Pill */}
        <div className="flex items-center gap-1.5 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800 font-mono text-xs">
          <span className="text-[10px] text-slate-400">|a|:</span>
          <strong className="text-cyan-300">
            {isConnected ? `${formatNumber(activeMag, 2)}` : '--'}
          </strong>
          <span className="text-[10px] text-slate-400">m/s²</span>
        </div>
      </div>

      {/* Component Tabs: Linear / Raw / Gravity */}
      <div className="grid grid-cols-3 gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800/80 mb-3 text-xs font-mono">
        <button
          type="button"
          onClick={() => setActiveTab('linear')}
          className={`py-1.5 px-2 rounded-lg text-center transition-colors ${
            activeTab === 'linear'
              ? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Linear Accel
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('raw')}
          className={`py-1.5 px-2 rounded-lg text-center transition-colors ${
            activeTab === 'raw'
              ? 'bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Raw Total
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('gravity')}
          className={`py-1.5 px-2 rounded-lg text-center transition-colors ${
            activeTab === 'gravity'
              ? 'bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Gravity Vector
        </button>
      </div>

      {/* Description Tooltip */}
      <p className="text-[11px] text-slate-400 mb-3 leading-snug">
        {currentDesc}
      </p>

      {/* 3-Axis Bipolar Bar Gauges */}
      <div className="space-y-2.5 flex-1">
        <BipolarBar
          value={currentVector.x}
          label="Surge (X-Axis)"
          axisName="+X"
          desc="Bow / Forward-Aft"
        />
        <BipolarBar
          value={currentVector.y}
          label="Sway (Y-Axis)"
          axisName="+Y"
          desc="Beam / Port-Starboard"
        />
        <BipolarBar
          value={currentVector.z}
          label="Heave (Z-Axis)"
          axisName="+Z"
          desc="Keel / Vertical"
        />
      </div>

      {/* Vector Magnitude Comparison Footer */}
      <div className="w-full mt-3 pt-2.5 border-t border-slate-800/80 grid grid-cols-3 gap-2 text-center font-mono text-[10px]">
        <div className="bg-slate-900/60 p-1.5 rounded-lg border border-slate-800">
          <span className="text-slate-400 block uppercase">|Linear|</span>
          <span className="text-cyan-300 font-bold">
            {isConnected ? `${formatNumber(linMag, 2)} m/s²` : '--'}
          </span>
        </div>
        <div className="bg-slate-900/60 p-1.5 rounded-lg border border-slate-800">
          <span className="text-slate-400 block uppercase">|Total Raw|</span>
          <span className="text-indigo-300 font-bold">
            {isConnected ? `${formatNumber(rawMag, 2)} m/s²` : '--'}
          </span>
        </div>
        <div className="bg-slate-900/60 p-1.5 rounded-lg border border-slate-800">
          <span className="text-slate-400 block uppercase">|Gravity|</span>
          <span className="text-emerald-300 font-bold">
            {isConnected ? `${formatNumber(gravMag, 2)} m/s²` : '--'}
          </span>
        </div>
      </div>
    </div>
  );
}
