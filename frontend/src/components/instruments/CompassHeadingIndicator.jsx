import React, { useRef, useEffect, useMemo } from 'react';
import { Compass, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

/**
 * CompassHeadingIndicator - Digital Marine Compass Rose
 * Implements a 360° rotating compass card with cardinal/intercardinal markers,
 * fixed lubber line, shortest-path angle unwrapping, digital heading readout,
 * and magnetometer calibration health checks.
 */
export function CompassHeadingIndicator({ imu, gps }) {
  const isConnected = Boolean(imu?.connected);
  const isStale = Boolean(imu?.is_stale);
  const orient = imu?.orientation;
  const calib = imu?.calibration || { mag: 0 };

  // Source selection: IMU fused heading -> IMU magnetic heading -> GPS course
  let heading = null;
  let headingSource = 'NONE';
  let headingValid = false;

  if (isConnected && orient?.heading_valid && typeof orient?.yaw === 'number' && !isNaN(orient.yaw)) {
    heading = (orient.yaw + 360) % 360;
    headingSource = 'IMU FUSED';
    headingValid = true;
  } else if (isConnected && typeof orient?.magnetic_heading_deg === 'number' && !isNaN(orient.magnetic_heading_deg)) {
    heading = (orient.magnetic_heading_deg + 360) % 360;
    headingSource = 'MAGNETIC';
    headingValid = true;
  } else if (gps?.course_deg !== null && gps?.course_deg !== undefined && !isNaN(Number(gps.course_deg))) {
    heading = (Number(gps.course_deg) + 360) % 360;
    headingSource = 'GNSS COG';
    headingValid = Boolean(gps.fix_valid);
  }

  // Shortest-path continuous angle accumulator to prevent 360° flip glitch
  const prevHeadingRef = useRef(heading ?? 0);
  const continuousHeadingRef = useRef(heading ?? 0);

  if (heading !== null) {
    const delta = ((heading - prevHeadingRef.current + 540) % 360) - 180;
    continuousHeadingRef.current += delta;
    prevHeadingRef.current = heading;
  }

  const continuousRotation = -continuousHeadingRef.current;

  // Geometry
  const CENTER = 150;
  const RADIUS = 110;

  // Generate 360 ticks
  const ticks = useMemo(() => {
    const items = [];
    for (let deg = 0; deg < 360; deg += 5) {
      const isCardinal = deg % 90 === 0;
      const isIntercardinal = deg % 45 === 0 && !isCardinal;
      const isMajor = deg % 30 === 0;
      const isMedium = deg % 10 === 0 && !isMajor;

      let len = 6;
      if (isCardinal) len = 14;
      else if (isIntercardinal) len = 11;
      else if (isMajor) len = 10;
      else if (isMedium) len = 8;

      let label = null;
      if (deg === 0) label = 'N';
      else if (deg === 45) label = 'NE';
      else if (deg === 90) label = 'E';
      else if (deg === 135) label = 'SE';
      else if (deg === 180) label = 'S';
      else if (deg === 225) label = 'SW';
      else if (deg === 270) label = 'W';
      else if (deg === 315) label = 'NW';
      else if (isMajor) label = String(deg).padStart(3, '0');

      items.push({ deg, len, isCardinal, isIntercardinal, isMajor, label });
    }
    return items;
  }, []);

  // Format 3-digit digital heading (e.g. "094.2")
  const formattedHeading = heading !== null
    ? (heading < 100 ? (heading < 10 ? `00${heading.toFixed(1)}` : `0${heading.toFixed(1)}`) : heading.toFixed(1))
    : '---.-';

  const isMagUncalibrated = isConnected && (calib.mag === 0 || calib.mag === null);

  return (
    <div className="bg-[#0B1220] border border-slate-800/90 rounded-2xl p-4 shadow-xl flex flex-col items-center relative overflow-hidden">
      {/* Header Bar */}
      <div className="w-full flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Compass className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Digital Compass
          </span>
          <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-1.5 py-0.5 rounded">
            ROSE
          </span>
        </div>

        {/* Source Badge */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono text-slate-400">SOURCE:</span>
          <span
            className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded border ${
              headingSource === 'IMU FUSED'
                ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                : headingSource === 'MAGNETIC'
                ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                : headingSource === 'GNSS COG'
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-slate-800 text-slate-500 border-slate-700'
            }`}
          >
            {headingSource}
          </span>
        </div>
      </div>

      {/* Main SVG Compass Rose */}
      <div className="relative w-[280px] h-[280px] sm:w-[300px] sm:h-[300px] flex items-center justify-center">
        <svg
          viewBox="0 0 300 300"
          className="w-full h-full select-none"
          style={{ filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.5))' }}
        >
          <defs>
            <radialGradient id="compass-face-grad" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#0a101d" />
              <stop offset="85%" stopColor="#070c16" />
              <stop offset="100%" stopColor="#04070d" />
            </radialGradient>
          </defs>

          {/* Outer Bezel Rim */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS + 24}
            fill="#090f1d"
            stroke="#1e293b"
            strokeWidth="3"
          />
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS + 12}
            fill="#040812"
            stroke="#334155"
            strokeWidth="1.5"
          />
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS}
            fill="url(#compass-face-grad)"
            stroke="#1e293b"
            strokeWidth="1"
          />

          {/* Rotating Compass Card */}
          <g
            transform={`rotate(${continuousRotation} ${CENTER} ${CENTER})`}
            className="transition-transform duration-100 ease-out"
          >
            {/* Ticks and Labels */}
            {ticks.map((t) => {
              const rad = ((t.deg - 90) * Math.PI) / 180;
              const x1 = CENTER + (RADIUS - 2) * Math.cos(rad);
              const y1 = CENTER + (RADIUS - 2) * Math.sin(rad);
              const x2 = CENTER + (RADIUS - 2 - t.len) * Math.cos(rad);
              const y2 = CENTER + (RADIUS - 2 - t.len) * Math.sin(rad);

              const strokeColor = t.deg === 0
                ? '#38bdf8'
                : t.isCardinal
                ? '#e2e8f0'
                : t.isIntercardinal
                ? '#94a3b8'
                : t.isMajor
                ? '#64748b'
                : '#334155';

              return (
                <g key={`tick-${t.deg}`}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={strokeColor}
                    strokeWidth={t.isCardinal ? '2.5' : t.isMajor ? '1.8' : '1'}
                  />

                  {t.label && (
                    <text
                      x={CENTER + (RADIUS - 24) * Math.cos(rad)}
                      y={CENTER + (RADIUS - 24) * Math.sin(rad) + 3.5}
                      textAnchor="middle"
                      fill={
                        t.deg === 0
                          ? '#38bdf8'
                          : t.isCardinal
                          ? '#f1f5f9'
                          : t.isIntercardinal
                          ? '#94a3b8'
                          : '#64748b'
                      }
                      fontSize={t.isCardinal ? '12' : t.isIntercardinal ? '10' : '8'}
                      fontFamily="monospace"
                      fontWeight={t.isCardinal ? 'bold' : 'normal'}
                    >
                      {t.label}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Cardinal Needle Lines across the card */}
            <line
              x1={CENTER}
              y1={CENTER - RADIUS + 32}
              x2={CENTER}
              y2={CENTER + RADIUS - 32}
              stroke="#1e293b"
              strokeWidth="1"
              strokeDasharray="3,3"
            />
            <line
              x1={CENTER - RADIUS + 32}
              y1={CENTER}
              x2={CENTER + RADIUS - 32}
              y2={CENTER}
              stroke="#1e293b"
              strokeWidth="1"
              strokeDasharray="3,3"
            />
          </g>

          {/* Central Fixed ASV Top-Down Vessel Icon */}
          <g id="vessel-center-silhouette" pointerEvents="none">
            {/* Inner dial ring */}
            <circle
              cx={CENTER}
              cy={CENTER}
              r="40"
              fill="#060c18"
              stroke="#1e293b"
              strokeWidth="1.5"
            />

            {/* Stylized ASV Catamaran Bow pointing UP (Lubber line direction) */}
            <path
              d={`M ${CENTER} ${CENTER - 28} 
                  L ${CENTER + 14} ${CENTER - 8} 
                  L ${CENTER + 14} ${CENTER + 20} 
                  L ${CENTER + 8} ${CENTER + 20} 
                  L ${CENTER + 6} ${CENTER + 6} 
                  L ${CENTER - 6} ${CENTER + 6} 
                  L ${CENTER - 8} ${CENTER + 20} 
                  L ${CENTER - 14} ${CENTER + 20} 
                  L ${CENTER - 14} ${CENTER - 8} Z`}
              fill="#0284c7"
              fillOpacity="0.4"
              stroke="#38bdf8"
              strokeWidth="1.5"
            />

            {/* Center Pivot Dot */}
            <circle cx={CENTER} cy={CENTER} r="3" fill="#38bdf8" stroke="#0c4a6e" strokeWidth="1" />
          </g>

          {/* Top Fixed Lubber Line (Fluorescent Amber Pointer at 12 o'clock) */}
          <polygon
            points={`${CENTER},${CENTER - RADIUS + 2} ${CENTER - 7},${CENTER - RADIUS - 12} ${CENTER + 7},${CENTER - RADIUS - 12}`}
            fill="#f59e0b"
            stroke="#78350f"
            strokeWidth="1"
          />

          {/* Bottom Fixed Reciprocal Index */}
          <polygon
            points={`${CENTER},${CENTER + RADIUS - 2} ${CENTER - 5},${CENTER + RADIUS + 8} ${CENTER + 5},${CENTER + RADIUS + 8}`}
            fill="#64748b"
            stroke="#1e293b"
            strokeWidth="1"
          />
        </svg>

        {/* Digital Heading Readout Pill Centered */}
        <div className="absolute top-[18px] flex flex-col items-center pointer-events-none">
          <div className="bg-slate-950/90 border border-slate-700/80 px-3 py-0.5 rounded-md shadow-md flex items-baseline gap-0.5">
            <span className="font-mono text-lg font-extrabold text-cyan-300 tracking-wider">
              {formattedHeading}
            </span>
            <span className="text-xs font-mono text-cyan-500 font-bold">°</span>
          </div>
        </div>
      </div>

      {/* Magnetometer Calibration Alert or Health Status Footer */}
      <div className="w-full mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
        {isMagUncalibrated ? (
          <div className="w-full bg-amber-950/40 border border-amber-800/60 rounded-lg p-2 flex items-center gap-2 text-amber-300">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <div className="text-[11px] leading-tight">
              <strong className="block font-semibold uppercase">Mag Uncalibrated (0/3)</strong>
              <span className="text-amber-400/80 text-[10px]">
                Rotate vehicle in figure-8 or 360° circle for full magnetic precision.
              </span>
            </div>
          </div>
        ) : (
          <div className="w-full flex items-center justify-between bg-slate-900/60 p-2 rounded-lg border border-slate-800 font-mono text-[11px]">
            <div className="flex items-center gap-1.5 text-slate-300">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Mag Calib: <strong>{calib.mag}/3</strong></span>
            </div>
            <span className="text-slate-400">
              True Hdg: <strong className="text-cyan-400">{formattedHeading}°</strong>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
