import { Wifi, WifiOff } from 'lucide-react';
import { Badge } from '../common/Badge';

export function ConnectionStatus({ wsConnected }) {
  return (
    <div className="flex items-center gap-2">
      <Badge variant={wsConnected ? 'success' : 'danger'} size="sm">
        {wsConnected ? (
          <>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            <Wifi className="w-3 h-3 text-emerald-400" />
            <span>LIVE TELEMETRY (5 Hz)</span>
          </>
        ) : (
          <>
            <WifiOff className="w-3 h-3 text-rose-400" />
            <span>RECONNECTING...</span>
          </>
        )}
      </Badge>
    </div>
  );
}
