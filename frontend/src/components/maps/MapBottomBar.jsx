import { Radio, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import { formatAge, getFixQualityLabel, getSatelliteMarkerColor, formatNumber } from '../../utils/formatters';

export function MapBottomBar({ gps }) {
  const satUsed = gps?.satellites_used ?? 0;
  const satVisible = gps?.satellites_visible ?? 0;
  const color = getSatelliteMarkerColor(satUsed);
  const isFix = gps?.fix_valid && !gps?.is_stale;
  const hasHdop = gps?.hdop !== null && gps?.hdop !== undefined && !isNaN(Number(gps?.hdop));

  return (
    <div className="absolute bottom-3 left-3 right-3 z-10 bg-slate-950/85 backdrop-blur-md border border-slate-800/90 rounded-xl px-4 py-2.5 shadow-2xl flex flex-wrap items-center justify-between gap-3 text-xs">
      {/* Fix Status */}
      <div className="flex items-center gap-2">
        {isFix ? (
          <CheckCircle className="w-4 h-4 text-emerald-400" />
        ) : (
          <AlertCircle className="w-4 h-4 text-amber-400" />
        )}
        <div>
          <span className="text-[10px] text-slate-400 block leading-tight">GPS FIX STATUS</span>
          <span className="font-semibold text-slate-200">
            {isFix ? getFixQualityLabel(gps?.fix_quality) : gps?.is_stale ? 'GPS Signal Stale' : 'No Valid Fix'}
          </span>
        </div>
      </div>

      {/* Satellite Info: Explicit separation between used vs visible */}
      <div className="flex items-center gap-4 border-l border-r border-slate-800/80 px-4">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
          <div>
            <span className="text-[10px] text-slate-400 block leading-tight">SATELLITES IN FIX</span>
            <span className="font-mono font-bold text-slate-100">{satUsed} used</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Radio className="w-3.5 h-3.5 text-slate-400" />
          <div>
            <span className="text-[10px] text-slate-400 block leading-tight">SATELLITES VISIBLE</span>
            <span className="font-mono font-bold text-slate-300">{satVisible || '--'} tracked</span>
          </div>
        </div>
      </div>

      {/* HDOP & Data Age */}
      <div className="flex items-center gap-4">
        {hasHdop && (
          <div>
            <span className="text-[10px] text-slate-400 block leading-tight">HDOP</span>
            <span className="font-mono font-bold text-cyan-300">{formatNumber(gps.hdop, 2)}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5 font-mono text-slate-400">
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span>{formatAge(gps?.data_age_seconds)}</span>
        </div>
      </div>
    </div>
  );
}
