import { Gamepad2, Compass } from 'lucide-react';
import { setOperatingMode } from '../../services/api';

export function ModeTabs({ currentMode, onModeChange }) {
  const handleSelect = async (mode) => {
    onModeChange(mode);
    try {
      await setOperatingMode(mode);
    } catch (err) {
      console.error("Failed to update operating mode:", err);
    }
  };

  return (
    <div className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
      <button
        onClick={() => handleSelect('manual')}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold tracking-wider uppercase transition-all ${
          currentMode === 'manual'
            ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20 font-bold'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
        }`}
      >
        <Gamepad2 className="w-4 h-4" />
        <span>Manual Mode</span>
      </button>

      <button
        onClick={() => handleSelect('semi_autonomous')}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold tracking-wider uppercase transition-all ${
          currentMode === 'semi_autonomous'
            ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20 font-bold'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
        }`}
      >
        <Compass className="w-4 h-4" />
        <span>Semi-Autonomous</span>
      </button>
    </div>
  );
}
