import { Card, StatRow } from '../common/Card';
import { Badge } from '../common/Badge';
import { Radio, Signal } from 'lucide-react';
import { getSatelliteMarkerColor, formatNumber } from '../../utils/formatters';

export function SatelliteQualityCard({ gps }) {
  const satUsed = gps.satellites_used ?? 0;
  const satVisible = gps.satellites_visible ?? 0;
  const color = getSatelliteMarkerColor(satUsed);
  const isHealthy = gps.connected && gps.fix_valid && !gps.is_stale;

  const variant = satUsed > 2 ? 'success' : satUsed === 2 ? 'warning' : 'danger';

  return (
    <Card title="GNSS Constellation & Precision" icon={Signal}>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">Fix Solution Sats</span>
          <div className="flex items-center gap-2 mt-0.5">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-lg font-bold font-mono text-white">{satUsed}</span>
            <span className="text-xs text-slate-500 font-mono">used</span>
          </div>
        </div>

        <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">In View</span>
          <div className="text-lg font-bold font-mono text-slate-300 mt-0.5">
            {satVisible || '--'} <span className="text-xs font-normal text-slate-500">tracked</span>
          </div>
        </div>
      </div>

      <div className="space-y-1 text-xs">
        <StatRow 
          label="Horizontal Dilution (HDOP)" 
          value={formatNumber(gps.hdop, 2)} 
          highlight={gps.hdop !== null && gps.hdop !== undefined && gps.hdop < 2.0} 
        />
        <StatRow 
          label="Positional Dilution (PDOP)" 
          value={formatNumber(gps.pdop, 2)} 
        />
        <StatRow 
          label="Vertical Dilution (VDOP)" 
          value={formatNumber(gps.vdop, 2)} 
        />
      </div>

      <div className="mt-3 pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
        <span>Signal Quality:</span>
        <Badge variant={variant} size="sm">
          {satUsed > 2 ? 'Optimal (>2 Sats)' : satUsed === 2 ? 'Marginal (2 Sats)' : 'Degraded (0-1 Sats)'}
        </Badge>
      </div>
    </Card>
  );
}
