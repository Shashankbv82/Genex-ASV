import React, { useState } from 'react';
import { Box, Eye, Navigation, ArrowUpRight } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

/**
 * ASVOrientation3D - Hardware-accelerated CSS 3D ASV Model
 * Renders a 3D isometric representation of the ASV catamaran hull
 * responding in real time to fused Pitch, Roll, and Yaw angles with
 * explicit FRD (Forward-Right-Down) coordinate axes and ocean datum grid.
 */
export function ASVOrientation3D({ imu }) {
  const isConnected = Boolean(imu?.connected);
  const orient = imu?.orientation;

  const rawPitch = orient?.pitch;
  const rawRoll = orient?.roll;
  const rawYaw = orient?.yaw;

  const pitch = typeof rawPitch === 'number' && !isNaN(rawPitch) ? rawPitch : 0;
  const roll = typeof rawRoll === 'number' && !isNaN(rawRoll) ? rawRoll : 0;
  const yaw = typeof rawYaw === 'number' && !isNaN(rawYaw) ? rawYaw : 0;

  // View angle toggle: 'isometric' or 'chase'
  const [viewAngle, setViewAngle] = useState('isometric');

  // Base camera angles for 3D stage
  // Isometric: tilted 60 deg down, 30 deg rotated
  // Chase: rear follow view
  const baseCamX = viewAngle === 'isometric' ? 62 : 75;
  const baseCamZ = viewAngle === 'isometric' ? -35 : 0;

  return (
    <div className="bg-[#0B1220] border border-slate-800/90 rounded-2xl p-4 shadow-xl flex flex-col items-center relative overflow-hidden">
      {/* Header Bar */}
      <div className="w-full flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Box className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            3D Vessel Attitude
          </span>
          <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-1.5 py-0.5 rounded">
            FRD
          </span>
        </div>

        {/* View Toggle */}
        <div className="flex items-center bg-slate-900/80 border border-slate-800 rounded-lg p-0.5 text-[10px] font-mono">
          <button
            type="button"
            onClick={() => setViewAngle('isometric')}
            className={`px-2 py-0.5 rounded ${
              viewAngle === 'isometric' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            ISO
          </button>
          <button
            type="button"
            onClick={() => setViewAngle('chase')}
            className={`px-2 py-0.5 rounded ${
              viewAngle === 'chase' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            CHASE
          </button>
        </div>
      </div>

      {/* 3D Viewport */}
      <div
        className="relative w-full h-[280px] sm:h-[300px] flex items-center justify-center select-none overflow-hidden rounded-xl bg-gradient-to-b from-[#070d18] via-[#050912] to-[#03060a] border border-slate-800/50"
        style={{ perspective: '850px' }}
      >
        {/* Ambient background depth grid */}
        <div
          className="absolute inset-0 opacity-20 pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(to right, #1e293b 1px, transparent 1px), linear-gradient(to bottom, #1e293b 1px, transparent 1px)',
            backgroundSize: '24px 24px',
          }}
        />

        {/* 3D World Stage */}
        <div
          className="relative transition-transform duration-100 ease-out"
          style={{
            width: '200px',
            height: '200px',
            transformStyle: 'preserve-3d',
            transform: `rotateX(${baseCamX}deg) rotateZ(${baseCamZ}deg)`,
          }}
        >
          {/* Ocean Water Plane Datum */}
          <div
            className="absolute -top-16 -left-16 w-80 h-80 rounded-full border border-cyan-500/20 opacity-40 pointer-events-none"
            style={{
              transform: 'translateZ(-40px)',
              background: 'radial-gradient(circle, rgba(6,182,212,0.08) 0%, rgba(2,132,199,0.02) 60%, transparent 80%)',
            }}
          >
            <div className="w-full h-full border border-dashed border-cyan-800/40 rounded-full animate-spin-slow" />
          </div>

          {/* ASV Hull Container with live attitude transforms */}
          <div
            className="absolute inset-0 flex items-center justify-center transition-transform duration-100 ease-out"
            style={{
              transformStyle: 'preserve-3d',
              // Standard aerospace/marine Euler rotation sequence:
              // Yaw around Z, Pitch around Y (transverse), Roll around X (longitudinal)
              transform: `rotateZ(${-yaw}deg) rotateY(${pitch}deg) rotateX(${roll}deg)`,
            }}
          >
            {/* Port Pontoon (Left) */}
            <div
              className="absolute w-5 h-36 bg-gradient-to-b from-slate-700 via-slate-800 to-slate-900 border border-slate-600/80 rounded-t-full shadow-lg"
              style={{
                transform: 'translateX(-32px) translateZ(0px)',
                boxShadow: '0 10px 20px rgba(0,0,0,0.6)',
              }}
            >
              {/* Port Nav Light (Red at Bow) */}
              <div className="absolute top-1 left-1 w-2 h-2 rounded-full bg-red-500 shadow-sm shadow-red-400 animate-pulse" />
              {/* Port Thruster Nozzle at Stern */}
              <div className="absolute -bottom-2 left-0.5 w-4 h-3 bg-cyan-900 border border-cyan-600/70 rounded-b" />
            </div>

            {/* Starboard Pontoon (Right) */}
            <div
              className="absolute w-5 h-36 bg-gradient-to-b from-slate-700 via-slate-800 to-slate-900 border border-slate-600/80 rounded-t-full shadow-lg"
              style={{
                transform: 'translateX(32px) translateZ(0px)',
                boxShadow: '0 10px 20px rgba(0,0,0,0.6)',
              }}
            >
              {/* Starboard Nav Light (Green at Bow) */}
              <div className="absolute top-1 right-1 w-2 h-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400 animate-pulse" />
              {/* Starboard Thruster Nozzle at Stern */}
              <div className="absolute -bottom-2 left-0.5 w-4 h-3 bg-cyan-900 border border-cyan-600/70 rounded-b" />
            </div>

            {/* Crossbeam Deck Platform */}
            <div
              className="absolute w-16 h-24 bg-gradient-to-b from-slate-800 to-slate-900 border border-cyan-500/40 rounded-lg shadow-xl flex flex-col items-center justify-between p-2"
              style={{
                transform: 'translateZ(10px)',
              }}
            >
              {/* Forward Bow Deck Point */}
              <div className="w-8 h-3 bg-cyan-500/30 border border-cyan-400/60 rounded-t-full flex items-center justify-center">
                <span className="text-[7px] font-mono text-cyan-200 font-bold">BOW</span>
              </div>

              {/* Superstructure Cabin */}
              <div className="w-10 h-10 bg-slate-950 border border-slate-700 rounded flex flex-col items-center justify-center shadow-inner">
                <div className="w-6 h-2 bg-cyan-400/40 rounded mb-1" />
                <span className="text-[7px] font-mono font-bold text-slate-300">ASV-01</span>
              </div>

              {/* GNSS Antenna Mast Dome */}
              <div
                className="w-4 h-4 rounded-full bg-amber-400 border border-amber-300 shadow-md flex items-center justify-center"
                style={{ transform: 'translateZ(14px)' }}
              >
                <div className="w-1.5 h-1.5 rounded-full bg-slate-950" />
              </div>
            </div>

            {/* 3D Reference Axis Arrows (FRD: Forward-Right-Down) */}
            <div className="absolute inset-0 pointer-events-none" style={{ transformStyle: 'preserve-3d' }}>
              {/* +X Axis (Bow / Forward) — Bright Cyan/Red Arrow pointing -Y on screen (forward) */}
              <div
                className="absolute top-1/2 left-1/2 w-0.5 h-24 bg-red-500 origin-top flex flex-col items-center"
                style={{
                  transform: 'rotateZ(180deg) translateZ(8px)',
                }}
              >
                <span
                  className="text-[9px] font-mono font-bold text-red-400 bg-black/80 px-1 rounded absolute -bottom-5"
                  style={{ transform: 'rotateX(-60deg)' }}
                >
                  +X (Bow)
                </span>
              </div>

              {/* +Y Axis (Starboard / Lateral) — Emerald Green Arrow pointing right */}
              <div
                className="absolute top-1/2 left-1/2 w-20 h-0.5 bg-emerald-500 origin-left flex items-center"
                style={{
                  transform: 'translateZ(8px)',
                }}
              >
                <span
                  className="text-[9px] font-mono font-bold text-emerald-400 bg-black/80 px-1 rounded absolute -right-6"
                  style={{ transform: 'rotateX(-60deg)' }}
                >
                  +Y (Stbd)
                </span>
              </div>

              {/* +Z Axis (Keel / Down) — Blue Arrow pointing down */}
              <div
                className="absolute top-1/2 left-1/2 w-0.5 h-16 bg-blue-500 origin-top flex flex-col items-center"
                style={{
                  transform: 'rotateX(-90deg) translateZ(0px)',
                }}
              >
                <span
                  className="text-[9px] font-mono font-bold text-blue-400 bg-black/80 px-1 rounded absolute -bottom-4"
                  style={{ transform: 'rotateX(90deg)' }}
                >
                  +Z (Keel)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Live Euler Angles Overlay */}
        <div className="absolute bottom-2 left-2 right-2 bg-slate-950/80 backdrop-blur border border-slate-800/80 rounded-lg p-2 grid grid-cols-3 gap-2 text-center font-mono text-[11px]">
          <div>
            <span className="text-[9px] text-slate-400 block uppercase">Heading (Yaw)</span>
            <span className="text-cyan-300 font-bold">
              {isConnected ? `${formatNumber(yaw, 1)}°` : '--'}
            </span>
          </div>
          <div>
            <span className="text-[9px] text-slate-400 block uppercase">Pitch</span>
            <span className="text-slate-200 font-bold">
              {isConnected ? `${formatNumber(pitch, 1)}°` : '--'}
            </span>
          </div>
          <div>
            <span className="text-[9px] text-slate-400 block uppercase">Roll</span>
            <span className="text-slate-200 font-bold">
              {isConnected ? `${formatNumber(roll, 1)}°` : '--'}
            </span>
          </div>
        </div>
      </div>

      {/* Coordinate Frame Convention Footer */}
      <div className="w-full mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
        <span className="font-mono text-[10px]">
          Mounting: <strong className="text-slate-200">+X Bow</strong>, <strong className="text-slate-200">+Y Starboard</strong>
        </span>
        <span className="font-mono text-[10px] text-cyan-400">
          Right-Handed FRD Frame
        </span>
      </div>
    </div>
  );
}
