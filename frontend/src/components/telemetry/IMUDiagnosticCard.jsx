import { Card, StatRow } from '../common/Card';
import { Compass, Activity, ArrowUp, CheckCircle2, AlertCircle } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

export function IMUDiagnosticCard({ imu }) {
  const isConnected = Boolean(imu?.connected);
  const isReady = imu?.lifecycle_state === 'ready';
  const headingValid = Boolean(imu?.orientation?.heading_valid);

  const calib = imu?.calibration || { sys: 0, gyro: 0, accel: 0, mag: 0 };
  const orient = imu?.orientation || { yaw: 0, pitch: 0, roll: 0 };
  const linAcc = imu?.acceleration || { x: 0, y: 0, z: 0 };
  const gyro = imu?.gyroscope || { x: 0, y: 0, z: 0 };

  const getCalibColor = (level) => {
    if (level === 3) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
    if (level >= 1) return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
    return 'bg-slate-800 text-slate-500 border-slate-700';
  };

  return (
    <Card title="IMU & ASV Heading Orientation" icon={Compass}>
      {/* Top Status & Heading Summary */}
      <div className="grid grid-cols-3 gap-2.5 mb-3">
        {/* Heading / Yaw */}
        <div className="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800 col-span-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider text-slate-400">Heading (Yaw)</span>
            {headingValid ? (
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            ) : (
              <AlertCircle className="w-3 h-3 text-amber-400" />
            )}
          </div>
          <div className="text-xl font-bold font-mono text-cyan-300 mt-1 flex items-baseline gap-0.5">
            {isConnected ? formatNumber(orient.yaw, 1) : '--'}
            <span className="text-xs text-slate-400">°</span>
          </div>
        </div>

        {/* Pitch */}
        <div className="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">Pitch (X-Axis)</span>
          <div className="text-base font-bold font-mono text-slate-200 mt-1 flex items-baseline gap-0.5">
            {isConnected ? formatNumber(orient.pitch, 1) : '--'}
            <span className="text-xs text-slate-400">°</span>
          </div>
        </div>

        {/* Roll */}
        <div className="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block">Roll (Y-Axis)</span>
          <div className="text-base font-bold font-mono text-slate-200 mt-1 flex items-baseline gap-0.5">
            {isConnected ? formatNumber(orient.roll, 1) : '--'}
            <span className="text-xs text-slate-400">°</span>
          </div>
        </div>
      </div>

      {/* Sensor Calibration Levels */}
      <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/80 mb-3">
        <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5 flex items-center justify-between">
          <span>BNO055 Fusion Calibration</span>
          <span className="font-mono text-[10px] text-slate-500">Scale: 0-3</span>
        </div>
        <div className="grid grid-cols-4 gap-1.5 text-center text-xs font-mono">
          <div className={`py-1 px-1.5 rounded border ${getCalibColor(calib.sys)}`}>
            <span className="block text-[9px] text-slate-400 uppercase">Sys</span>
            <strong>{calib.sys}/3</strong>
          </div>
          <div className={`py-1 px-1.5 rounded border ${getCalibColor(calib.gyro)}`}>
            <span className="block text-[9px] text-slate-400 uppercase">Gyro</span>
            <strong>{calib.gyro}/3</strong>
          </div>
          <div className={`py-1 px-1.5 rounded border ${getCalibColor(calib.accel)}`}>
            <span className="block text-[9px] text-slate-400 uppercase">Accel</span>
            <strong>{calib.accel}/3</strong>
          </div>
          <div className={`py-1 px-1.5 rounded border ${getCalibColor(calib.mag)}`}>
            <span className="block text-[9px] text-slate-400 uppercase">Mag</span>
            <strong>{calib.mag}/3</strong>
          </div>
        </div>
      </div>

      {/* Detailed Inertial Vector Stats */}
      <div className="space-y-1 text-xs">
        <StatRow
          label="Linear Accel X (Bow)"
          value={isConnected ? formatNumber(linAcc.x, 2) : '--'}
          unit="m/s²"
        />
        <StatRow
          label="Linear Accel Y (Beam)"
          value={isConnected ? formatNumber(linAcc.y, 2) : '--'}
          unit="m/s²"
        />
        <StatRow
          label="Angular Rate Z (Yaw Rate)"
          value={isConnected ? formatNumber(gyro.z, 3) : '--'}
          unit="rad/s"
        />
        <StatRow
          label="Forward Body Vector"
          value="+X Axis (Physical Bow)"
        />
      </div>
    </Card>
  );
}
