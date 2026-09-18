import { Card } from '../common/Card';
import { MapPin } from 'lucide-react';
import { formatCoordinate, formatNumber } from '../../utils/formatters';

export function CoordinatesCard({ gps }) {
  return (
    <Card title="Current Position" icon={MapPin}>
      <div className="space-y-3">
        <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800/80">
          <div className="flex justify-between items-baseline mb-1">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Latitude</span>
            <span className="text-[10px] text-slate-500 font-mono">WGS84</span>
          </div>
          <div className="text-xl font-bold font-mono text-cyan-300 tracking-tight">
            {formatCoordinate(gps?.latitude, true)}
          </div>
        </div>

        <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800/80">
          <div className="flex justify-between items-baseline mb-1">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Longitude</span>
            <span className="text-[10px] text-slate-500 font-mono">WGS84</span>
          </div>
          <div className="text-xl font-bold font-mono text-cyan-300 tracking-tight">
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
