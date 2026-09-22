import { Card, StatRow } from '../common/Card';
import { Badge } from '../common/Badge';
import { 
  Radio, 
  Sliders, 
  ShieldCheck, 
  ShieldAlert, 
  Zap, 
  Power, 
  Activity, 
  AlertTriangle, 
  Cpu, 
  CheckCircle2, 
  XCircle,
  Wifi,
  WifiOff
} from 'lucide-react';

export function ManualModePanel({ rc = {}, manualControl = {}, motors = {}, safety = {} }) {
  // RC Receiver State
  const rcConnected = rc.connected ?? false;
  const rcHealthy = (rc.signal_health === 'HEALTHY');
  const validFrames = rc.valid_frames ?? 0;
  const failsafeActive = rc.failsafe_active ?? true;
  // Authoritative RC validity condition: healthy, connected, active frames, and no failsafe
  const hasValidRC = rcConnected && rcHealthy && (validFrames > 0) && !failsafeActive;

  const rcAge = rc.data_age_seconds !== undefined && rc.data_age_seconds !== null 
    ? rc.data_age_seconds.toFixed(2) + 's' 
    : '--';
  const protocol = rc.protocol || 'PPM';
  const ch1Raw = rc.ch1_raw ?? null;
  const ch3Raw = rc.ch3_raw ?? null;
  const ch5Raw = rc.ch5_raw ?? null;
  const normSteering = hasValidRC ? (rc.normalized_steering ?? 0.0) : 0.0;
  const normThrottle = hasValidRC ? (rc.normalized_throttle ?? 0.0) : 0.0;
  const ch5Active = hasValidRC && Boolean(rc.manual_requested);

  // Manual Mode Controller State
  const ctrlState = manualControl.state || (rcConnected ? 'STANDBY' : 'DISCONNECTED');
  const isActive = manualControl.is_active ?? false;
  const throttleZero = manualControl.throttle_zero_confirmed ?? false;
  const lockoutReason = manualControl.lockout_reason;
  const motorsInhibited = manualControl.motors_inhibited ?? true;

  // Motor / ESC State
  const motorsHardwareEnabled = motors.motors_enabled ?? false;
  const isNeutralized = motors.neutralized ?? true;
  const leftPwmUs = motors.left_pwm_us ?? 1500.0;
  const rightPwmUs = motors.right_pwm_us ?? 1500.0;
  const leftPercent = motors.left_percent ?? ((leftPwmUs - 1500) / 5.0);
  const rightPercent = motors.right_percent ?? ((rightPwmUs - 1500) / 5.0);
  const estopOverride = motors.safety_override_active ?? safety.obstacle_estop_active ?? false;

  // Steering indicator calculation (centered at 50%, range 0% to 100%)
  const steeringPosPercent = Math.max(0, Math.min(100, 50 + normSteering * 50));
  // Throttle bar percent (0% to 100%)
  const throttlePercent = Math.max(0, Math.min(100, normThrottle * 100));

  // Determine state badge styling
  const getStateBadge = () => {
    switch (ctrlState) {
      case 'ACTIVE':
        return (
          <Badge variant="success" size="md">
            <span className="flex items-center gap-1.5 animate-pulse">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              ACTIVE / ARMED
            </span>
          </Badge>
        );
      case 'STANDBY':
        return (
          <Badge variant="warning" size="md">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              STANDBY
            </span>
          </Badge>
        );
      case 'FAILSAFE':
        return (
          <Badge variant="danger" size="md">
            <span className="flex items-center gap-1.5 animate-pulse">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
              FAILSAFE (SIGNAL LOST)
            </span>
          </Badge>
        );
      case 'LOCKED_OUT':
        return (
          <Badge variant="danger" size="md">
            <span className="flex items-center gap-1.5">
              <XCircle className="w-3.5 h-3.5 text-rose-400" />
              LOCKED OUT ({lockoutReason || 'ESTOP'})
            </span>
          </Badge>
        );
      default:
        return (
          <Badge variant="neutral" size="md">
            <WifiOff className="w-3.5 h-3.5" />
            DISCONNECTED
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Banner: Status, Arming State, and Bench-Test Advisory */}
      <div className="bg-[#0E1524] border border-slate-800/80 rounded-2xl p-4 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-xl ${
            isActive 
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
              : 'bg-slate-800/80 text-slate-400 border border-slate-700/60'
          }`}>
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-wide uppercase text-slate-200">
                Manual Mode Subsystem
              </h2>
              {getStateBadge()}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              FlySky FS-iA10B &bull; GPIO 22 &bull; Pre-Mix Rate Limiter &bull; PCA9685 ESCs
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {/* Zero-Throttle Startup Interlock Badge */}
          <span className={`px-2.5 py-1 rounded-md border flex items-center gap-1.5 ${
            !hasValidRC
              ? 'bg-slate-900/80 text-slate-400 border-slate-800'
              : throttleZero
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
          }`}>
            {!hasValidRC ? (
              <>
                <WifiOff className="w-3.5 h-3.5 text-slate-500" />
                <span>Zero Throttle: NOT CONFIRMED (NO RC LINK)</span>
              </>
            ) : throttleZero ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Zero Throttle Confirmed (READY)</span>
              </>
            ) : (
              <>
                <AlertTriangle className="w-3.5 h-3.5 animate-pulse" />
                <span>Zero Throttle Required to Arm (LOWER STICK)</span>
              </>
            )}
          </span>

          {/* Bench Mode Safe Inhibit Badge */}
          <span className={`px-2.5 py-1 rounded-md border flex items-center gap-1.5 ${
            motorsHardwareEnabled
              ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse'
              : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
          }`}>
            <Power className="w-3.5 h-3.5" />
            <span>
              {motorsHardwareEnabled ? 'PROPULSION ENERGIZED' : 'BENCH MODE (Motors Inhibited)'}
            </span>
          </span>
        </div>
      </div>

      {/* 3-Card Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        
        {/* CARD 1: FlySky RC Receiver & Link Telemetry */}
        <Card
          title="RC Link & Receiver"
          icon={Radio}
          badge={
            <Badge variant={rcHealthy ? 'success' : rcConnected ? 'warning' : 'danger'} size="sm">
              {rcHealthy ? 'SIGNAL HEALTHY' : rcConnected ? 'SIGNAL LOST' : 'DISCONNECTED'}
            </Badge>
          }
        >
          <div className="space-y-2.5 text-xs">
            <StatRow
              label="Receiver Protocol"
              value={`${protocol} (BCM GPIO 22)`}
              highlight
            />
            <StatRow
              label="Link Status"
              value={
                rcHealthy ? (
                  <span className="text-emerald-400 font-semibold flex items-center gap-1">
                    <Wifi className="w-3.5 h-3.5" />
                    CONNECTED
                  </span>
                ) : rcConnected ? (
                  <span className="text-amber-400 font-semibold flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    SIGNAL LOST
                  </span>
                ) : (
                  <span className="text-rose-400 font-semibold flex items-center gap-1">
                    <WifiOff className="w-3.5 h-3.5" />
                    DISCONNECTED
                  </span>
                )
              }
            />
            <StatRow
              label="Packet Age"
              value={rcAge}
              alert={rc.data_age_seconds > 0.20}
            />
            <StatRow
              label="Failsafe Status"
              value={
                rc.failsafe_active ? (
                  <span className="text-rose-400 font-bold">ACTIVE (NEUTRAL)</span>
                ) : (
                  <span className="text-emerald-400">NOMINAL</span>
                )
              }
              alert={rc.failsafe_active}
            />

            <div className="pt-2 border-t border-slate-800">
              <span className="text-slate-400 font-medium block mb-1.5">Raw Channel Pulses</span>
              <div className="grid grid-cols-3 gap-2 font-mono text-center">
                <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-2">
                  <div className="text-[10px] text-slate-400">CH1 STR</div>
                  <div className="text-slate-200 font-bold mt-0.5">
                    {hasValidRC && ch1Raw !== null ? `${ch1Raw} µs` : '-- / NO DATA'}
                  </div>
                </div>
                <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-2">
                  <div className="text-[10px] text-slate-400">CH3 THR</div>
                  <div className="text-slate-200 font-bold mt-0.5">
                    {hasValidRC && ch3Raw !== null ? `${ch3Raw} µs` : '-- / NO DATA'}
                  </div>
                </div>
                <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-2">
                  <div className="text-[10px] text-slate-400">CH5 SWD</div>
                  <div className={`font-bold mt-0.5 ${hasValidRC && ch5Active ? 'text-emerald-400' : 'text-slate-400'}`}>
                    {hasValidRC && ch5Raw !== null ? `${ch5Raw} µs` : '-- / NO DATA'}
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
              <span>Valid Frames: <strong className="text-slate-200 font-mono">{rc.valid_frames ?? 0}</strong></span>
              <span>Glitches: <strong className="text-slate-200 font-mono">{rc.glitch_count ?? 0}</strong></span>
            </div>
          </div>
        </Card>

        {/* CARD 2: Stick Inputs & Interlocks */}
        <Card
          title="Manual Control Input"
          icon={Sliders}
          badge={
            <Badge variant={hasValidRC && ch5Active ? 'success' : 'neutral'} size="sm">
              CH5 SWITCH: {!hasValidRC ? 'NO RC LINK' : ch5Active ? 'ON' : 'OFF'}
            </Badge>
          }
        >
          <div className="space-y-4 text-xs">
            {/* Steering Control Widget */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-slate-400 font-medium">Steering Input (CH1)</span>
                <span className="font-mono text-slate-200 font-semibold">
                  {!hasValidRC ? '-- / NO DATA' : normSteering > 0 ? `+${normSteering.toFixed(2)} (R)` : normSteering < 0 ? `${normSteering.toFixed(2)} (L)` : '0.00 (CTR)'}
                </span>
              </div>
              
              {/* Graphical Steering Bar */}
              <div className="relative w-full h-5 bg-slate-950 rounded-lg border border-slate-800 overflow-hidden flex items-center">
                {/* Center marker line */}
                <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-slate-700 z-10 -translate-x-1/2" />
                {/* Direction fill from center */}
                {normSteering < 0 && (
                  <div 
                    className="absolute right-1/2 top-0 bottom-0 bg-cyan-500/30 border-r border-cyan-400 transition-all duration-75"
                    style={{ width: `${Math.abs(normSteering) * 50}%` }}
                  />
                )}
                {normSteering > 0 && (
                  <div 
                    className="absolute left-1/2 top-0 bottom-0 bg-cyan-500/30 border-l border-cyan-400 transition-all duration-75"
                    style={{ width: `${normSteering * 50}%` }}
                  />
                )}
                {/* Indicator cursor */}
                <div 
                  className="absolute top-1 bottom-1 w-2.5 bg-cyan-400 rounded-full -translate-x-1/2 shadow-md shadow-cyan-500/50 transition-all duration-75 z-20"
                  style={{ left: `${steeringPosPercent}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-slate-500 mt-1 font-mono">
                <span>&larr; FULL LEFT</span>
                <span>CENTER</span>
                <span>FULL RIGHT &rarr;</span>
              </div>
            </div>

            {/* Throttle Control Widget */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-slate-400 font-medium">Forward Throttle (CH3)</span>
                <span className="font-mono text-cyan-300 font-bold">
                  {!hasValidRC ? '-- / NO DATA' : `${throttlePercent.toFixed(1)}%`}
                </span>
              </div>
              
              {/* Graphical Throttle Bar */}
              <div className="w-full h-4 bg-slate-950 rounded-lg border border-slate-800 overflow-hidden p-0.5">
                <div 
                  className="h-full rounded-md bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-75"
                  style={{ width: `${throttlePercent}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-slate-500 mt-1 font-mono">
                <span>IDLE (0%)</span>
                <span>CRUISE (50%)</span>
                <span>MAX (100%)</span>
              </div>
            </div>

            {/* Arming & Interlock Overview */}
            <div className="pt-2 border-t border-slate-800 space-y-1.5">
              <StatRow
                label="CH5 Manual Arm Switch"
                value={
                  !hasValidRC ? (
                    <span className="text-slate-500 font-mono">DISARMED / NO RC LINK</span>
                  ) : ch5Active ? (
                    <span className="text-emerald-400 font-bold">ACTIVE (ENGAGED)</span>
                  ) : (
                    <span className="text-slate-400">INACTIVE (DISARMED)</span>
                  )
                }
              />
              <StatRow
                label="Zero-Throttle Interlock"
                value={
                  !hasValidRC ? (
                    <span className="text-amber-400 font-mono">NOT CONFIRMED (NO RC LINK)</span>
                  ) : throttleZero ? (
                    <span className="text-emerald-400 font-medium">CONFIRMED (READY)</span>
                  ) : (
                    <span className="text-amber-400 font-medium">REQUIRED (LOWER STICK)</span>
                  )
                }
              />
              <StatRow
                label="Motor Power Inhibit"
                value={
                  motorsInhibited ? (
                    <span className="text-cyan-400 font-mono">INHIBITED (SAFE)</span>
                  ) : (
                    <span className="text-emerald-400 font-mono">ACTIVE (OUTPUTTING)</span>
                  )
                }
              />
            </div>
          </div>
        </Card>

        {/* CARD 3: PCA9685 Hardware & ESC Outputs */}
        <Card
          title="Differential ESC Driver"
          icon={Zap}
          badge={
            <Badge variant={estopOverride ? 'danger' : isNeutralized ? 'warning' : 'success'} size="sm">
              {estopOverride ? 'E-STOP HALT' : isNeutralized ? 'NEUTRAL (1500µs)' : 'PROPULSION ACTIVE'}
            </Badge>
          }
        >
          <div className="space-y-4 text-xs">
            {/* Left ESC */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-slate-300">Left Thruster (Ch 0)</span>
                <span className="font-mono text-cyan-300 font-bold">
                  {leftPwmUs.toFixed(1)} µs
                </span>
              </div>
              <div className="w-full h-3 bg-slate-950 rounded border border-slate-800 overflow-hidden">
                <div 
                  className="h-full bg-cyan-400 transition-all duration-75"
                  style={{ width: `${Math.max(0, Math.min(100, ((leftPwmUs - 1000) / 1000) * 100))}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-slate-500 mt-1 font-mono">
                <span>Output: {leftPercent > 0 ? `+${leftPercent.toFixed(1)}%` : `${leftPercent.toFixed(1)}%`}</span>
                <span>Ticks: {Math.round((leftPwmUs / 20000) * 4095)} / 4095</span>
              </div>
            </div>

            {/* Right ESC */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3">
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-slate-300">Right Thruster (Ch 1)</span>
                <span className="font-mono text-cyan-300 font-bold">
                  {rightPwmUs.toFixed(1)} µs
                </span>
              </div>
              <div className="w-full h-3 bg-slate-950 rounded border border-slate-800 overflow-hidden">
                <div 
                  className="h-full bg-cyan-400 transition-all duration-75"
                  style={{ width: `${Math.max(0, Math.min(100, ((rightPwmUs - 1000) / 1000) * 100))}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-slate-500 mt-1 font-mono">
                <span>Output: {rightPercent > 0 ? `+${rightPercent.toFixed(1)}%` : `${rightPercent.toFixed(1)}%`}</span>
                <span>Ticks: {Math.round((rightPwmUs / 20000) * 4095)} / 4095</span>
              </div>
            </div>

            {/* PCA9685 Hardware Status */}
            <div className="pt-2 border-t border-slate-800 space-y-1">
              <StatRow
                label="PWM Controller"
                value="PCA9685 (I2C Bus 1 @ 0x40)"
              />
              <StatRow
                label="PWM Frequency"
                value="50 Hz (20,000 µs Period)"
              />
              <StatRow
                label="Safety Override"
                value={
                  estopOverride ? (
                    <span className="text-rose-400 font-bold animate-pulse">ESTOP LOCKED</span>
                  ) : (
                    <span className="text-slate-400">CLEAR</span>
                  )
                }
                alert={estopOverride}
              />
            </div>
          </div>
        </Card>

      </div>
    </div>
  );
}
