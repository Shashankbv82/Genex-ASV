import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { Compass, CheckCircle2, AlertTriangle, XCircle, Clock, Database } from 'lucide-react';
import { getFixQualityLabel, formatAge, formatLastKnownAge } from '../../utils/formatters';

export function GPSStatusCard({ gps }) {
  const isLive = gps?.position_source === 'live' && gps?.live_fix_valid && !gps?.is_stale;
  const isLastKnown = gps?.position_source === 'last_known';
  const isConnected = Boolean(gps?.connected);

  return (
    <Card title="GPS Receiver Status" icon={Compass}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            {isLive ? (
              <>
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                <span>{getFixQualityLabel(gps.fix_quality)}</span>
              </>
            ) : isLastKnown ? (
              <>
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 animate-pulse" />
                <span className="text-amber-300">LAST KNOWN POSITION — ACQUIRING LIVE GPS</span>
              </>
            ) : isConnected ? (
              <>
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
                <span>{gps.is_stale ? 'GPS Data Stale' : 'Acquiring Fix...'}</span>
              </>
            ) : (
              <>
                <XCircle className="w-5 h-5 text-rose-400 shrink-0" />
                <span>GPS Disconnected</span>
              </>
            )}
          </div>
          <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
            {isLastKnown
              ? `Cached fix saved ${formatLastKnownAge(gps?.last_known_fix_age_seconds)}`
              : `Port: ${gps?.source || '/dev/ttyS0'} (115200 8N1)`}
          </span>
        </div>
        <Badge variant={isLive ? 'success' : isLastKnown ? 'warning' : isConnected ? 'warning' : 'danger'}>
          {isLive ? 'LIVE GPS FIX' : isLastKnown ? 'CACHED FIX' : `${(gps?.fix_type || 'none').toUpperCase()} FIX`}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/80 text-xs">
        <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/50">
          <span className="text-slate-400 block text-[11px]">Data Freshness</span>
          <span className="font-mono font-semibold text-slate-200 flex items-center gap-1 mt-0.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            {formatAge(gps?.data_age_seconds)}
          </span>
        </div>
        <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/50">
          <span className="text-slate-400 block text-[11px]">Position Source</span>
          <span className={`font-mono font-semibold mt-0.5 flex items-center gap-1 ${
            isLive ? 'text-emerald-400' : isLastKnown ? 'text-amber-400' : 'text-slate-400'
          }`}>
            {isLastKnown ? <Database className="w-3.5 h-3.5" /> : null}
            {isLive ? 'LIVE GNSS FIX' : isLastKnown ? 'PERSISTENT CACHE' : isConnected ? 'ACQUIRING...' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </Card>
  );
}
