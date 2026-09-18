import { Card, StatRow } from '../common/Card';
import { Gauge, Navigation } from 'lucide-react';
import { formatSpeed, formatCourse, formatNumber } from '../../utils/formatters';

export function MotionDataCard({ gps }) {
  return (
    <Card title="ASV Kinematics & Velocity" icon={Gauge}>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">Ground Speed</span>
          <div className="text-lg font-bold font-mono text-slate-100 mt-0.5">
            {formatSpeed(gps.speed_mps)}
          </div>
        </div>
        <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">Course (COG)</span>
          <div className="text-lg font-bold font-mono text-slate-100 mt-0.5 flex items-center gap-1">
            <Navigation className="w-4 h-4 text-cyan-400 transform rotate-45" />
            {formatCourse(gps.course_deg)}
          </div>
        </div>
      </div>

      <div className="space-y-1 text-xs">
        <StatRow 
          label="Speed (Knots)" 
          value={formatNumber(gps.speed_knots, 2)} 
          unit="kts" 
        />
        <StatRow 
          label="Speed (m/s)" 
          value={formatNumber(gps.speed_mps, 2)} 
          unit="m/s" 
        />
      </div>
    </Card>
  );
}
