import React from 'react';
import { Mountain, Radio, Satellite, ShieldCheck, AlertCircle } from 'lucide-react';
import { formatNumber, getFixQualityLabel } from '../../utils/formatters';

/**
 * AltitudeGauge - WGS-84 GNSS Vertical Status Display
 * Visualizes GNSS-derived ellipsoidal altitude with vertical tape meter,
 * fix quality indicators, satellite tracking count, and explicit WGS-84 source label.
 */
export function AltitudeGauge({ gps }) {
  const isConnected = Boolean(gps?.connected);
  const fixValid = Boolean(gps?.fix_valid);
  const altM = gps?.altitude_m;
  const fixType = gps?.fix_type || 'none';
  const satellitesUsed = gps?.satellites_used ?? 0;
  const vdop = gps?.vdop;

  // Numerical altitude
  const validAlt = typeof altM === 'number' && !isNaN(altM) ? altM : null;

  // Vertical scale parameters (visual tape)
  const centerAlt = validAlt ?? 0;
  // Render marks from -20m to +20m around current altitude
  const marks = [];
  const minMark = Math.floor((centerAlt - 15) / 5) * 5;
  for (let a = minMark; a <= minMark + 30; a += 5) {
    marks.push(a);
  }

  return (
    <div className="bg-[#0B1220] border border-slate-800/90 rounded-2xl p-4 shadow-xl flex flex-col relative overflow-hidden">
      {/* Header Bar */}
      <div className="w-full flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Mountain className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            GNSS Altitude (WGS-84)
          </span>
        </div>
        <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-1.5 py-0.5 rounded">
          GPS VERT
        </span>
      </div>

      {/* Main Altimeter Readout and Tape */}
      <div className="flex items-center gap-4 bg-slate-950/80 border border-slate-800 rounded-xl p-3 mb-3">
        {/* Prominent Large Digital Value */}
        <div className="flex-1">
          <span className="text-[10px] uppercase font-mono text-slate-400 block mb-0.5">
            Ellipsoidal Height
          </span>
          <div className="flex items-baseline gap-1 font-mono">
            <span className="text-2xl sm:text-3xl font-extrabold text-cyan-300">
              {validAlt !== null ? formatNumber(validAlt, 1) : '--.-'}
            </span>
            <span className="text-sm font-bold text-slate-400">meters</span>
          </div>

          <div className="mt-2 flex items-center gap-1.5 text-xs">
            {fixValid ? (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded">
                <ShieldCheck className="w-3 h-3" />
                {gps?.fix_quality ? getFixQualityLabel(gps.fix_quality) : '3D Fix'}
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded">
                <AlertCircle className="w-3 h-3" />
                No Fix
              </span>
            )}
          </div>
        </div>

        {/* Vertical Tape Visualizer */}
        <div className="relative w-16 h-28 bg-slate-900 border border-slate-700/80 rounded-lg overflow-hidden flex flex-col justify-between py-1 select-none">
          {/* Center pointer indicator */}
          <div className="absolute top-1/2 -translate-y-1/2 left-0 right-0 h-5 bg-cyan-500/20 border-y border-cyan-400/60 flex items-center justify-between px-1 pointer-events-none z-10">
            <div className="w-1.5 h-1.5 bg-cyan-400 rotate-45" />
            <span className="text-[9px] font-mono font-bold text-cyan-200">ALT</span>
          </div>

          {/* Dynamic vertical tick tape */}
          <div className="flex flex-col-reverse justify-around h-full py-1 text-right pr-2">
            {marks.map((m) => (
              <div key={`alt-${m}`} className="flex items-center justify-end gap-1.5">
                <span className="font-mono text-[9px] text-slate-400">{m}m</span>
                <div className="w-2 h-0.5 bg-slate-600" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Satellite Quality & Dilution Context */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Satellite className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[10px]">Satellites</span>
          </div>
          <span className="font-bold text-slate-200">{satellitesUsed} SVs</span>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Radio className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-[10px]">VDOP</span>
          </div>
          <span className="font-bold text-slate-200">
            {vdop !== null && vdop !== undefined ? formatNumber(vdop, 2) : '--'}
          </span>
        </div>
      </div>

      {/* Important Marine Warning Footer */}
      <div className="w-full mt-3 pt-2 border-t border-slate-800/80 text-[10px] text-slate-500 leading-tight">
        * Note: GNSS altitude is referenced to the WGS-84 ellipsoid and does not represent echo sounder water depth or local chart datum.
      </div>
    </div>
  );
}
