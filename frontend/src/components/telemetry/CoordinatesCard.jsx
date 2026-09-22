import { Card } from '../common/Card';
import { MapPin } from 'lucide-react';
import { formatCoordinate, formatNumber } from '../../utils/formatters';

export function CoordinatesCard({ gps }) {
  const isLive = gps?.position_source === 'live' && gps?.live_fix_valid && !gps?.is_stale;
  const isLastKnown = gps?.position_source === 'last_known';

  return (
    <Card title="Current Position" icon={MapPin}>
      <div className="space-y-3">
        {/* Source indicator banner */}
        <div className="flex items-center justify-between px-1">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Position Datum</span>
          {isLive ? (
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
              ● LIVE FIX
            </span>
          ) : isLastKnown ? (
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">
              ▲ LAST KNOWN (CACHED)
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-800 text-slate-400 border border-slate-700">
              NO FIX
            </span>
          )}
        </div>

        <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800/80">
          <div className="flex justify-between items-baseline mb-1">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Latitude</span>
            <span className="text-[10px] text-slate-500 font-mono">WGS84</span>
          </div>
          <div className={`text-xl font-bold font-mono tracking-tight ${isLastKnown ? 'text-amber-300' : 'text-cyan-300'}`}>
            {formatCoordinate(gps?.latitude, true)}
          </div>
        </div>

        <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800/80">
          <div className="flex justify-between items-baseline mb-1">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Longitude</span>
            <span className="text-[10px] text-slate-500 font-mono">WGS84</span>
          </div>
          <div className={`text-xl font-bold font-mono tracking-tight ${isLastKnown ? 'text-amber-300' : 'text-cyan-300'}`}>
            {formatCoordinate(gps?.longitude, false)}
          </div>
        </div>

        <div className="flex justify-between items-center px-1 pt-1 text-xs">
          <span className="text-slate-400">Altitude (MSL):</span>
          <span className="font-mono font-medium text-slate-200">
            {gps?.altitude_m !== null && gps?.altitude_m !== undefined ? (formatNumber(gps.altitude_m, 1) + ' m') : '-- m'}
          </span>
        </div>
      </div>
    </Card>
  );
}
