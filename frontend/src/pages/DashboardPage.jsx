import { useState } from 'react';
import { useTelemetry } from '../hooks/useTelemetry';
import { Header } from '../components/layout/Header';
import { ModeTabs } from '../components/layout/ModeTabs';
import { LiveMap } from '../components/maps/LiveMap';
import { GPSStatusCard } from '../components/telemetry/GPSStatusCard';
import { CoordinatesCard } from '../components/telemetry/CoordinatesCard';
import { SatelliteQualityCard } from '../components/telemetry/SatelliteQualityCard';
import { MotionDataCard } from '../components/telemetry/MotionDataCard';
import { IMUDiagnosticCard } from '../components/telemetry/IMUDiagnosticCard';
import { SystemHealthCard } from '../components/telemetry/SystemHealthCard';
import { Shield, Navigation2, Sliders } from 'lucide-react';

export function DashboardPage() {
  const { telemetry, wsConnected } = useTelemetry();
  const [activeMode, setActiveMode] = useState(telemetry.operating_mode || 'manual');

  const gps = telemetry.gps;
  const filtered = telemetry.filtered;
  const imu = telemetry.imu;
  const system = telemetry.system;

  return (
    <div className="min-h-screen bg-[#070B12] text-slate-100 flex flex-col font-sans">
      <Header wsConnected={wsConnected} operatingMode={activeMode} />

      <main className="flex-1 p-4 lg:p-6 max-w-[1800px] w-full mx-auto flex flex-col gap-5">
        {/* Top Control Bar: Mode Switcher & ASV Status Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0E1524] border border-slate-800/80 p-3 rounded-2xl shadow-xl">
          <div className="flex items-center gap-3">
            <ModeTabs currentMode={activeMode} onModeChange={setActiveMode} />
            <div className="hidden md:flex items-center gap-2 text-xs text-slate-400 pl-3 border-l border-slate-800">
              <Shield className="w-4 h-4 text-cyan-400" />
              <span>
                {activeMode === 'manual' 
                  ? 'Manual Thrust & Steering Mode Selected' 
                  : 'Semi-Autonomous GPS Waypoint Mode Selected'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end sm:self-auto text-xs font-mono text-slate-400">
            <span>UART Source: <strong className="text-cyan-400">/dev/ttyS0</strong></span>
            <span className="hidden sm:inline">•</span>
            <span>Baud: <strong className="text-slate-200">115200</strong></span>
          </div>
        </div>

        {/* Primary Operational View: Map & Telemetry Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 flex-1 items-start">
          {/* Main Viewport: Satellite Map (7 Columns on large screens) */}
          <div className="xl:col-span-7 h-[540px] xl:h-[720px] flex flex-col">
            <LiveMap gps={gps} filtered={filtered} imu={imu} />
          </div>

          {/* Telemetry & Subsystem Panels (5 Columns on large screens) */}
          <div className="xl:col-span-5 flex flex-col gap-4">
            {/* Mode-Specific Context Banner */}
            {activeMode === 'manual' ? (
              <div className="bg-cyan-950/30 border border-cyan-800/50 rounded-xl p-3.5 flex items-start gap-3">
                <Sliders className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
                <div className="text-xs">
                  <h4 className="font-semibold text-cyan-300 uppercase tracking-wide">Manual Control Mode Ready</h4>
                  <p className="text-slate-400 mt-0.5 leading-relaxed">
                    Vehicle GPS telemetry is streaming continuously. Thruster mixer and ESC driver controls will be integrated in the upcoming Manual Control milestone.
                  </p>
                </div>
              </div>
            ) : (
              <div className="bg-indigo-950/30 border border-indigo-800/50 rounded-xl p-3.5 flex items-start gap-3">
                <Navigation2 className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
                <div className="text-xs">
                  <h4 className="font-semibold text-indigo-300 uppercase tracking-wide">Semi-Autonomous Navigation Ready</h4>
                  <p className="text-slate-400 mt-0.5 leading-relaxed">
                    Live GPS fix established. Waypoint queue, geo-fencing, and path-tracking tools will be linked in the Autonomous Mission milestone without restructuring this layout.
                  </p>
                </div>
              </div>
            )}

            {/* Telemetry Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <GPSStatusCard gps={gps} />
              <CoordinatesCard gps={gps} />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <SatelliteQualityCard gps={gps} />
              <MotionDataCard gps={gps} />
            </div>

            <IMUDiagnosticCard imu={imu} />

            <SystemHealthCard system={system} />
          </div>
        </div>
      </main>
    </div>
  );
}

