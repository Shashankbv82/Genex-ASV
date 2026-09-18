import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { Compass, CheckCircle2, AlertTriangle, XCircle, Clock } from 'lucide-react';
import { getFixQualityLabel, formatAge } from '../../utils/formatters';

export function GPSStatusCard({ gps }) {
  const isHealthy = gps.connected && gps.fix_valid && !gps.is_stale;
  
  return (
    <Card title="GPS Receiver Status" icon={Compass}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            {isHealthy ? (
              <>
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span>{getFixQualityLabel(gps.fix_quality)}</span>
              </>
            ) : gps.connected ? (
              <>
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <span>{gps.is_stale ? 'GPS Data Stale' : 'Acquiring Fix...'}</span>
              </>
            ) : (
              <>
                <XCircle className="w-5 h-5 text-rose-400" />
                <span>GPS Disconnected</span>
              </>
            )}
          </div>
          <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
            Port: {gps.source || '/dev/ttyS0'} (115200 8N1)
          </span>
        </div>
        <Badge variant={isHealthy ? 'success' : gps.connected ? 'warning' : 'danger'}>
          {gps.fix_type.toUpperCase()} FIX
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/80 text-xs">
        <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/50">
          <span className="text-slate-400 block text-[11px]">Data Freshness</span>
          <span className="font-mono font-semibold text-slate-200 flex items-center gap-1 mt-0.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            {formatAge(gps.data_age_seconds)}
          </span>
        </div>
        <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/50">
          <span className="text-slate-400 block text-[11px]">Stream State</span>
          <span className={`font-mono font-semibold mt-0.5 block ${gps.connected ? 'text-emerald-400' : 'text-rose-400'}`}>
            {gps.connected ? 'UART STREAMING' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </Card>
  );
}
