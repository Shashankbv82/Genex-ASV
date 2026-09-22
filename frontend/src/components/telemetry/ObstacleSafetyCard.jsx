import { Card, StatRow } from '../common/Card';
import { Badge } from '../common/Badge';
import { ShieldAlert, ShieldCheck, AlertTriangle, Cpu } from 'lucide-react';

export function ObstacleSafetyCard({ safety = {}, operatingMode = 'manual' }) {
  const isConnected = safety.ir_sensor_connected ?? false;
  const isDetected = safety.ir_obstacle_detected ?? false;
  const isEstop = safety.obstacle_estop_active ?? false;
  const gpioLevel = safety.ir_gpio_level ?? 1;

  return (
    <Card 
      title="IR Obstacle Safety Monitor" 
      icon={isEstop || isDetected ? ShieldAlert : ShieldCheck}
      badge={
        <Badge variant={isConnected ? 'success' : 'danger'} size="sm">
          {isConnected ? 'LIVE / ACTIVE' : 'OFFLINE'}
        </Badge>
      }
    >
      <div className="space-y-2.5 text-xs">
        {/* Real-time Proximity Status Highlight */}
        <div className="flex items-center justify-between pb-2 border-b border-slate-800">
          <span className="text-slate-300 font-medium">Obstacle Status</span>
          <Badge 
            variant={isDetected ? 'danger' : 'success'} 
            size="md"
          >
            {isDetected ? (
              <span className="flex items-center gap-1.5 animate-pulse text-rose-300 font-bold">
                <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
                OBSTACLE DETECTED!
              </span>
            ) : (
              <span className="text-emerald-400 font-semibold">
                CLEAR / NO OBSTACLE
              </span>
            )}
          </Badge>
        </div>

        {/* E-stop Latch Status */}
        <StatRow
          label="Safety E-Stop"
          value={
            isEstop ? (
              <span className="text-rose-400 font-bold flex items-center gap-1">
                LATCHED ({safety.obstacle_estop_reason || 'HALT'})
              </span>
            ) : (
              <span className="text-slate-400 font-medium">
                STANDBY (Normal)
              </span>
            )
          }
          alert={isEstop}
        />

        {/* Operating Mode Context */}
        <StatRow
          label="Operating Mode"
          value={
            operatingMode === 'semi_autonomous' ? (
              <span className="text-indigo-400 font-semibold">SEMI-AUTONOMOUS</span>
            ) : (
              <span className="text-cyan-400 font-medium">MANUAL</span>
            )
          }
        />

        {/* GPIO Hardware Diagnostic */}
        <StatRow
          label="Hardware Pin"
          value="BCM GPIO17 (Pin 11, Pull-Up)"
        />

        <StatRow
          label="Logic Level"
          value={
            gpioLevel === 0 ? (
              <span className="text-amber-400 font-mono">LOW (0.0V) [Active]</span>
            ) : (
              <span className="text-emerald-400 font-mono">HIGH (3.3V) [Clear]</span>
            )
          }
        />

        <StatRow
          label="Debounce Filter"
          value="30 ms Hardware Filter"
        />

        <StatRow
          label="Detection Mode"
          value="Proximity Threshold Only"
        />

        {/* Sensor Disclaimer Notice */}
        <div className="mt-3 p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-start gap-2 text-[11px] text-slate-400 leading-relaxed">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <span className="text-slate-200 font-medium">Binary Proximity Advisory: </span>
            The LM393 comparator outputs binary threshold detection only (adjusted via onboard potentiometer). Numerical distance in centimeters is uncalibrated and not measured.
          </div>
        </div>
      </div>
    </Card>
  );
}
