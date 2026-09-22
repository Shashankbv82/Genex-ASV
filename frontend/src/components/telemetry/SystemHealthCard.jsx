import { Card, StatRow } from '../common/Card';
import { Badge } from '../common/Badge';
import { Cpu, Wifi, HardDrive, Activity } from 'lucide-react';

export function SystemHealthCard({ system }) {
  const isLteUp = system.lte_connected;
  const cpuTemp = system.cpu_temp_c;
  const isHot = cpuTemp && cpuTemp > 70;

  return (
    <Card title="Pi 3B+ System Health" icon={Activity}>
      <div className="space-y-2.5 text-xs">
        <div className="flex items-center justify-between pb-2 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Wifi className={`w-4 h-4 ${isLteUp ? 'text-emerald-400' : 'text-slate-500'}`} />
            <span className="text-slate-300 font-medium">Cellular LTE (usb0)</span>
          </div>
          <Badge variant={isLteUp ? 'success' : 'neutral'} size="sm">
            {isLteUp ? (system.lte_ip || 'Connected') : 'Disconnected'}
          </Badge>
        </div>

        <StatRow 
          label="SoC Temperature" 
          value={cpuTemp !== null ? `${cpuTemp}°C` : '--'} 
          alert={isHot}
        />
        <StatRow 
          label="Power / Throttling" 
          value={system.throttled_description || 'Normal'} 
          highlight={system.throttled_description === 'Normal'}
        />
        <StatRow 
          label="RAM Usage" 
          value={system.memory_used_mb ? `${system.memory_used_mb} MB / ${system.memory_total_mb} MB` : '--'} 
        />
        <StatRow 
          label="System Uptime" 
          value={system.uptime_seconds ? `${Math.round(system.uptime_seconds / 60)} mins` : '--'} 
        />
      </div>
    </Card>
  );
}
