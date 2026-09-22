import React, { useMemo } from 'react';
import { ShieldAlert, Activity } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

/**
 * AttitudeIndicator - Aviation / Marine Primary Flight Display Artificial Horizon
 * Renders an aerospace-grade SVG attitude sphere with pitch ladder, bank roll index,
 * fixed ASV reticle, and live numerical readouts.
 */
export function AttitudeIndicator({ imu }) {
  const isConnected = Boolean(imu?.connected);
  const isStale = Boolean(imu?.is_stale);
  const orient = imu?.orientation;

  const rawPitch = orient?.pitch;
  const rawRoll = orient?.roll;

  const pitch = typeof rawPitch === 'number' && !isNaN(rawPitch) ? rawPitch : 0;
  const roll = typeof rawRoll === 'number' && !isNaN(rawRoll) ? rawRoll : 0;

  // Pitch ladder scale: pixels per degree
  const PITCH_SCALE = 2.4;
  // Radius of the attitude ball display
  const RADIUS = 110;
  const CENTER = 150;

  // Horizon vertical translation: negative pitch (nose up) shifts horizon down
  const horizonTranslateY = -pitch * PITCH_SCALE;
  // Horizon roll rotation
  const horizonRotate = -roll;

  // Extreme attitude warning (e.g. > 35 deg roll or pitch)
  const isAttitudeWarning = Math.abs(pitch) > 35 || Math.abs(roll) > 40;

  // Direction labels
  const pitchDirection = pitch > 0.5 ? 'NOSE DN' : pitch < -0.5 ? 'NOSE UP' : 'LEVEL';
  const rollDirection = roll > 0.5 ? 'STBD' : roll < -0.5 ? 'PORT' : 'LEVEL';

  // Bank angle scale markers: [angle, tickLength, isMajor]
  const bankTicks = [
    { angle: -60, len: 12, major: true },
    { angle: -45, len: 10, major: false },
    { angle: -30, len: 12, major: true },
    { angle: -20, len: 8, major: false },
    { angle: -10, len: 8, major: false },
    { angle: 0, len: 14, major: true },
    { angle: 10, len: 8, major: false },
    { angle: 20, len: 8, major: false },
    { angle: 30, len: 12, major: true },
    { angle: 45, len: 10, major: false },
    { angle: 60, len: 12, major: true },
  ];

  // Pitch ladder rungs
  const pitchLadderRungs = useMemo(() => {
    const rungs = [];
    const steps = [-30, -25, -20, -15, -10, -5, 5, 10, 15, 20, 25, 30];
    for (const deg of steps) {
      const y = -deg * PITCH_SCALE;
      const isPositive = deg > 0;
      const width = Math.abs(deg) % 10 === 0 ? 50 : 26;
      rungs.push({
        deg,
        y,
        width,
        isPositive,
        isMajor: Math.abs(deg) % 10 === 0,
      });
    }
    return rungs;
  }, []);

  return (
    <div className="bg-[#0B1220] border border-slate-800/90 rounded-2xl p-4 shadow-xl flex flex-col items-center relative overflow-hidden">
      {/* Header Bar */}
      <div className="w-full flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Attitude Indicator
          </span>
          <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-1.5 py-0.5 rounded">
            PFD
          </span>
        </div>
        {isAttitudeWarning && (
          <div className="flex items-center gap-1 text-[10px] font-bold text-amber-400 bg-amber-950/60 border border-amber-800/80 px-2 py-0.5 rounded-full animate-bounce">
            <ShieldAlert className="w-3 h-3" />
            <span>ATTITUDE WARN</span>
          </div>
        )}
      </div>

      {/* Main SVG Instrument */}
      <div className="relative w-[280px] h-[280px] sm:w-[300px] sm:h-[300px] flex items-center justify-center">
        <svg
          viewBox="0 0 300 300"
          className="w-full h-full select-none"
          style={{ filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.5))' }}
        >
          <defs>
            {/* Circular mask for the moving attitude ball */}
            <clipPath id="horizon-clip">
              <circle cx={CENTER} cy={CENTER} r={RADIUS} />
            </clipPath>

            {/* Sky gradient */}
            <linearGradient id="sky-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#034694" />
              <stop offset="60%" stopColor="#0284c7" />
              <stop offset="100%" stopColor="#38bdf8" />
            </linearGradient>

            {/* Ground gradient */}
            <linearGradient id="ground-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#451a03" />
              <stop offset="50%" stopColor="#1e1b18" />
              <stop offset="100%" stopColor="#090d16" />
            </linearGradient>

            {/* Bezel Metallic Rim */}
            <linearGradient id="bezel-rim" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#334155" />
              <stop offset="40%" stopColor="#0f172a" />
              <stop offset="70%" stopColor="#1e293b" />
              <stop offset="100%" stopColor="#020617" />
            </linearGradient>
          </defs>

          {/* Outer Instrument Bezel */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS + 25}
            fill="url(#bezel-rim)"
            stroke="#1e293b"
            strokeWidth="3"
          />
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS + 12}
            fill="#080d1a"
            stroke="#334155"
            strokeWidth="1.5"
          />

          {/* Moving Attitude Ball (Masked) */}
          <g clipPath="url(#horizon-clip)">
            {/* The rotating & translating horizon group */}
            <g
              transform={`rotate(${horizonRotate} ${CENTER} ${CENTER}) translate(0 ${horizonTranslateY})`}
              className="transition-transform duration-100 ease-out"
            >
              {/* Sky background */}
              <rect
                x={CENTER - 300}
                y={CENTER - 600}
                width="600"
                height="600"
                fill="url(#sky-gradient)"
              />

              {/* Ground background */}
              <rect
                x={CENTER - 300}
                y={CENTER}
                width="600"
                height="600"
                fill="url(#ground-gradient)"
              />

              {/* High-contrast Horizon Line */}
              <line
                x1={CENTER - 300}
                y1={CENTER}
                x2={CENTER + 300}
                y2={CENTER}
                stroke="#ffffff"
                strokeWidth="2.5"
              />

              {/* Pitch Ladder Rungs */}
              {pitchLadderRungs.map((rung) => {
                const yPos = CENTER + rung.y;
                const halfW = rung.width / 2;
                const tickDirection = rung.isPositive ? 4 : -4; // Points toward horizon
                return (
                  <g key={`rung-${rung.deg}`}>
                    {/* Left bar */}
                    <line
                      x1={CENTER - halfW}
                      y1={yPos}
                      x2={CENTER - 12}
                      y2={yPos}
                      stroke="#ffffff"
                      strokeWidth={rung.isMajor ? '2' : '1.2'}
                      strokeDasharray={rung.deg < 0 ? '4,3' : 'none'}
                    />
                    {/* Left vertical tick */}
                    <line
                      x1={CENTER - halfW}
                      y1={yPos}
                      x2={CENTER - halfW}
                      y2={yPos + tickDirection}
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />

                    {/* Right bar */}
                    <line
                      x1={CENTER + 12}
                      y1={yPos}
                      x2={CENTER + halfW}
                      y2={yPos}
                      stroke="#ffffff"
                      strokeWidth={rung.isMajor ? '2' : '1.2'}
                      strokeDasharray={rung.deg < 0 ? '4,3' : 'none'}
                    />
                    {/* Right vertical tick */}
                    <line
                      x1={CENTER + halfW}
                      y1={yPos}
                      x2={CENTER + halfW}
                      y2={yPos + tickDirection}
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />

                    {/* Degree labels on major rungs */}
                    {rung.isMajor && (
                      <>
                        <text
                          x={CENTER - halfW - 6}
                          y={yPos + 3}
                          textAnchor="end"
                          fill="#ffffff"
                          fontSize="9"
                          fontFamily="monospace"
                          fontWeight="bold"
                        >
                          {Math.abs(rung.deg)}
                        </text>
                        <text
                          x={CENTER + halfW + 6}
                          y={yPos + 3}
                          textAnchor="start"
                          fill="#ffffff"
                          fontSize="9"
                          fontFamily="monospace"
                          fontWeight="bold"
                        >
                          {Math.abs(rung.deg)}
                        </text>
                      </>
                    )}
                  </g>
                );
              })}
            </g>
          </g>

          {/* Bank Angle Scale on Outer Bezel Arc */}
          <g>
            {bankTicks.map((tick) => {
              const rad = ((tick.angle - 90) * Math.PI) / 180;
              const rInner = RADIUS + 1;
              const rOuter = RADIUS + tick.len;
              const x1 = CENTER + rInner * Math.cos(rad);
              const y1 = CENTER + rInner * Math.sin(rad);
              const x2 = CENTER + rOuter * Math.cos(rad);
              const y2 = CENTER + rOuter * Math.sin(rad);

              return (
                <line
                  key={`bank-${tick.angle}`}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={tick.major ? '#38bdf8' : '#64748b'}
                  strokeWidth={tick.major ? '2' : '1.2'}
                />
              );
            })}

            {/* Top Fixed Roll Pointer (White Down-Pointing Triangle at 0 deg) */}
            <polygon
              points={`${CENTER},${CENTER - RADIUS - 2} ${CENTER - 6},${CENTER - RADIUS - 12} ${CENTER + 6},${CENTER - RADIUS - 12}`}
              fill="#ffffff"
              stroke="#0f172a"
              strokeWidth="1"
            />

            {/* Dynamic Roll Pointer (Sky Blue Up-Pointing Triangle on rotating ring) */}
            <g
              transform={`rotate(${horizonRotate} ${CENTER} ${CENTER})`}
              className="transition-transform duration-100 ease-out"
            >
              <polygon
                points={`${CENTER},${CENTER - RADIUS + 2} ${CENTER - 5},${CENTER - RADIUS + 10} ${CENTER + 5},${CENTER - RADIUS + 10}`}
                fill="#38bdf8"
                stroke="#0284c7"
                strokeWidth="1"
              />
            </g>
          </g>

          {/* Inner Bezel Ring Shadow */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS}
            fill="none"
            stroke="#0f172a"
            strokeWidth="3"
            opacity="0.7"
          />

          {/* Fixed ASV Centerline Reticle (Aviation Aircraft / Vessel Silhouette) */}
          <g id="fixed-asv-reticle" pointerEvents="none">
            {/* Center Reference Dot */}
            <circle cx={CENTER} cy={CENTER} r="3" fill="#eab308" stroke="#713f12" strokeWidth="1" />

            {/* Left Wing Bar */}
            <path
              d={`M ${CENTER - 55} ${CENTER} L ${CENTER - 20} ${CENTER} L ${CENTER - 20} ${CENTER + 6} L ${CENTER - 45} ${CENTER + 6} Z`}
              fill="#eab308"
              stroke="#854d0e"
              strokeWidth="1"
            />

            {/* Right Wing Bar */}
            <path
              d={`M ${CENTER + 55} ${CENTER} L ${CENTER + 20} ${CENTER} L ${CENTER + 20} ${CENTER + 6} L ${CENTER + 45} ${CENTER + 6} Z`}
              fill="#eab308"
              stroke="#854d0e"
              strokeWidth="1"
            />

            {/* Center Keel / Pointer Notch */}
            <path
              d={`M ${CENTER - 3} ${CENTER - 15} L ${CENTER + 3} ${CENTER - 15} L ${CENTER} ${CENTER - 6} Z`}
              fill="#eab308"
              stroke="#854d0e"
              strokeWidth="1"
            />
          </g>

          {/* Disconnected / Stale Watermark Overlay */}
          {(!isConnected || isStale) && (
            <g>
              <rect
                x={CENTER - RADIUS}
                y={CENTER - RADIUS}
                width={RADIUS * 2}
                height={RADIUS * 2}
                rx={RADIUS}
                fill="#020617"
                fillOpacity="0.75"
              />
              <text
                x={CENTER}
                y={CENTER - 10}
                textAnchor="middle"
                fill="#f87171"
                fontSize="12"
                fontFamily="sans-serif"
                fontWeight="bold"
                letterSpacing="1"
              >
                {!isConnected ? 'IMU OFFLINE' : 'DATA STALE'}
              </text>
              <text
                x={CENTER}
                y={CENTER + 10}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize="9"
                fontFamily="sans-serif"
              >
                {!isConnected ? 'Sensor disconnected' : 'Check I2C bus connection'}
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* Numeric Readouts Footer */}
      <div className="w-full grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-slate-800/80 font-mono text-xs">
        {/* Pitch Stat */}
        <div className="bg-slate-900/80 rounded-lg p-2 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 block uppercase">Pitch</span>
            <span className="text-base font-bold text-slate-100">
              {isConnected ? `${formatNumber(pitch, 1)}°` : '--'}
            </span>
          </div>
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
              pitch > 0.5
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : pitch < -0.5
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                : 'bg-slate-800 text-slate-400'
            }`}
          >
            {isConnected ? pitchDirection : '--'}
          </span>
        </div>

        {/* Roll Stat */}
        <div className="bg-slate-900/80 rounded-lg p-2 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 block uppercase">Roll</span>
            <span className="text-base font-bold text-slate-100">
              {isConnected ? `${formatNumber(roll, 1)}°` : '--'}
            </span>
          </div>
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
              Math.abs(roll) > 0.5
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                : 'bg-slate-800 text-slate-400'
            }`}
          >
            {isConnected ? rollDirection : '--'}
          </span>
        </div>
      </div>
    </div>
  );
}
