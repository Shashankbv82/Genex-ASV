import { useState, useEffect } from 'react';
import { Anchor, ShieldCheck } from 'lucide-react';
import { ConnectionStatus } from '../status/ConnectionStatus';

export function Header({ wsConnected, operatingMode, currentView = 'mission', onViewChange }) {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTimeStr(now.toUTCString().split(' ').slice(4, 5)[0] + ' UTC');
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="bg-[#0B0F19]/90 border-b border-slate-800/80 px-4 sm:px-6 py-3 backdrop-blur-md sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3">
      {/* Brand & Vessel ID */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 p-0.5 flex items-center justify-center shadow-lg shadow-cyan-500/20">
          <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
            <Anchor className="w-5 h-5 text-cyan-400" />
          </div>
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-extrabold tracking-wider text-white uppercase">GENEX ASV</h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              VESSEL #01
            </span>
          </div>
          <span className="text-[11px] text-slate-400 font-mono block leading-none mt-0.5">
            Autonomous Surface Vehicle Telemetry & Navigation Station
          </span>
        </div>
      </div>

      {/* Center High-Contrast View Switcher */}
      {onViewChange && (
        <div className="flex items-center bg-slate-950 border border-slate-800/90 p-1 rounded-xl shadow-inner">
          <button
            type="button"
            onClick={() => onViewChange('mission')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              currentView === 'mission'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <span>🛰️</span>
            <span>Mission Control</span>
          </button>
          <button
            type="button"
            onClick={() => onViewChange('instruments')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              currentView === 'instruments'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <span>🧭</span>
            <span>Navigation Instruments</span>
          </button>
        </div>
      )}

      {/* Right status items */}
      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800">
          <span>{timeStr}</span>
        </div>

        <ConnectionStatus wsConnected={wsConnected} />
      </div>
    </header>
  );
}
