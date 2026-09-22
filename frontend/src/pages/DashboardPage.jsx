import { useState, useEffect } from 'react';
import { useTelemetry } from '../hooks/useTelemetry';
import { Header } from '../components/layout/Header';
import { ModeTabs } from '../components/layout/ModeTabs';
import { LiveMap } from '../components/maps/LiveMap';
import { GPSStatusCard } from '../components/telemetry/GPSStatusCard';
import { CoordinatesCard } from '../components/telemetry/CoordinatesCard';
import { SatelliteQualityCard } from '../components/telemetry/SatelliteQualityCard';
import { MotionDataCard } from '../components/telemetry/MotionDataCard';
import { IMUDiagnosticCard } from '../components/telemetry/IMUDiagnosticCard';
import { ObstacleSafetyCard } from '../components/telemetry/ObstacleSafetyCard';
import { SystemHealthCard } from '../components/telemetry/SystemHealthCard';
import { ManualModePanel } from '../components/manual/ManualModePanel';
import { InstrumentsPage } from './InstrumentsPage';
import { resetObstacleEstop } from '../services/api';
import { Shield, Navigation2, Sliders, AlertOctagon, RotateCcw, AlertCircle } from 'lucide-react';

export function DashboardPage() {
  const { telemetry, wsConnected } = useTelemetry();
  const [activeMode, setActiveMode] = useState(telemetry.operating_mode || 'manual');
  const [currentView, setCurrentView] = useState('mission'); // 'mission' | 'instruments'
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState(null);

  useEffect(() => {
    if (telemetry.operating_mode && telemetry.operating_mode !== activeMode) {
      setActiveMode(telemetry.operating_mode);
    }
  }, [telemetry.operating_mode]);

  const handleResetEstop = async () => {
    setResetting(true);
    setResetError(null);
    try {
      await resetObstacleEstop();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to reset E-stop';
      setResetError(msg);
    } finally {
      setResetting(false);
    }
  };

  const handleViewChange = (view) => {
    setCurrentView(view);
    if (view === 'mission') {
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    }
  };

  const gps = telemetry.gps;
  const filtered = telemetry.filtered;
  const imu = telemetry.imu;
  const system = telemetry.system;
  const safety = telemetry.safety || {};
  const rc = telemetry.rc || {};
  const manualControl = telemetry.manual_control || {};
  const motors = telemetry.motors || {};

  return (
    <div className="min-h-screen bg-[#070B12] text-slate-100 flex flex-col font-sans">
      <Header
        wsConnected={wsConnected}
        operatingMode={activeMode}
        currentView={currentView}
        onViewChange={handleViewChange}
      />

      {/* View 1: Mission Control (Map + Telemetry Cards) */}
      <div className={currentView === 'mission' ? 'contents' : 'hidden'}>
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

          {/* Manual Mode Subsystem Panel (Direct FlySky RC & Differential ESC Control) */}
          {activeMode === 'manual' && (
            <ManualModePanel 
              rc={rc} 
              manualControl={manualControl} 
              motors={motors} 
              safety={safety} 
            />
          )}

          {/* Primary Operational View: Map & Telemetry Grid */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 flex-1 items-start">
            {/* Main Viewport: Satellite Map (7 Columns on large screens) */}
            <div className="xl:col-span-7 h-[540px] xl:h-[720px] flex flex-col">
              <LiveMap gps={gps} filtered={filtered} imu={imu} />
            </div>

            {/* Telemetry & Subsystem Panels (5 Columns on large screens) */}
            <div className="xl:col-span-5 flex flex-col gap-4">
              {/* Emergency E-Stop Action Banner (High Visibility Alert) */}
              {safety.obstacle_estop_active && (
                <div className="bg-gradient-to-r from-rose-950/90 to-red-950/90 border-2 border-rose-600 rounded-2xl p-4 shadow-2xl shadow-rose-950/50 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-pulse">
                  <div className="flex items-start gap-3">
                    <div className="p-2.5 rounded-xl bg-rose-600/30 text-rose-400 border border-rose-500/40 flex-shrink-0">
                      <AlertOctagon className="w-6 h-6 animate-bounce" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-rose-200 text-sm tracking-wide uppercase">
                          Obstacle E-Stop Active — Autonomous Propulsion Locked
                        </h3>
                        <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-mono font-bold border border-rose-500/30">
                          LATCHED
                        </span>
                      </div>
                      <p className="text-xs text-rose-300/90 mt-1">
                        Reason: <strong className="text-rose-100 font-mono">{safety.obstacle_estop_reason || 'IR_OBSTACLE_DETECTED'}</strong>
                        <span className="mx-2">•</span>
                        Path Sensor: <strong className={safety.ir_obstacle_detected ? 'text-amber-300' : 'text-emerald-300'}>
                          {safety.ir_obstacle_detected ? 'OBSTACLE STILL DETECTED IN PATH' : 'CLEAR (Path Unobstructed)'}
                        </strong>
                      </p>
                      {resetError && (
                        <p className="text-xs text-amber-300 font-medium mt-1.5 flex items-center gap-1.5">
                          <AlertCircle className="w-3.5 h-3.5" />
                          {resetError}
                        </p>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={handleResetEstop}
                    disabled={resetting || safety.ir_obstacle_detected || !safety.reset_allowed}
                    className={`px-4 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-2 flex-shrink-0 shadow-lg ${
                      safety.ir_obstacle_detected || !safety.reset_allowed
                        ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed opacity-60'
                        : 'bg-rose-500 hover:bg-rose-400 text-slate-950 shadow-rose-500/30 cursor-pointer active:scale-95'
                    }`}
                    title={safety.ir_obstacle_detected ? "Cannot reset: Clear physical obstacle from sensor path first" : "Click to reset E-stop and restore manual propulsion"}
                  >
                    <RotateCcw className={`w-4 h-4 ${resetting ? 'animate-spin' : ''}`} />
                    <span>{resetting ? 'Resetting...' : 'Reset Obstacle E-Stop'}</span>
                  </button>
                </div>
              )}

              {/* Mode-Specific Context Banner */}
              {activeMode === 'manual' ? (
                <div className="bg-cyan-950/30 border border-cyan-800/50 rounded-xl p-3.5 flex items-start gap-3">
                  <Sliders className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
                  <div className="text-xs">
                    <h4 className="font-semibold text-cyan-300 uppercase tracking-wide">Direct Manual Control Active</h4>
                    <p className="text-slate-400 mt-0.5 leading-relaxed">
                      FlySky RC stick commands (CH1 Steering, CH3 Throttle, CH5 Arm Switch) are mixing to dual differential ESC channels via PCA9685 PWM hardware.
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

              <ObstacleSafetyCard safety={safety} operatingMode={activeMode} />

              <SystemHealthCard system={system} />
            </div>
          </div>
        </main>
      </div>

      {/* View 2: Navigation Instruments Panel */}
      {currentView === 'instruments' && (
        <InstrumentsPage telemetry={telemetry} wsConnected={wsConnected} />
      )}
    </div>
  );
}

