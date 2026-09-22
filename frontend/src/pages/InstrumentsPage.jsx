import React from 'react';
import { Compass, Box, Activity, Mountain, Cpu, ShieldCheck, AlertCircle } from 'lucide-react';
import { AttitudeIndicator } from '../components/instruments/AttitudeIndicator';
import { CompassHeadingIndicator } from '../components/instruments/CompassHeadingIndicator';
import { ASVOrientation3D } from '../components/instruments/ASVOrientation3D';
import { InertialGauges } from '../components/instruments/InertialGauges';
import { GyroscopeGauge } from '../components/instruments/GyroscopeGauge';
import { AltitudeGauge } from '../components/instruments/AltitudeGauge';
import { IMUCalibrationStatusPanel } from '../components/instruments/IMUCalibrationStatusPanel';
import { formatNumber } from '../utils/formatters';

/**
 * InstrumentsPage - Dedicated Avionic & Marine Navigation Instrument Panel
 * Integrates Attitude Indicator, Digital Compass Rose, 3D Vessel Attitude Model,
 * Inertial Acceleration, Gyroscope & Rate of Turn, Altitude, and Calibration panels.
 */
export function InstrumentsPage({ telemetry, wsConnected }) {
  const imu = telemetry?.imu;
  const gps = telemetry?.gps;
  const isConnected = Boolean(imu?.connected);
  const orient = imu?.orientation;

  const heading = orient?.yaw !== null && orient?.yaw !== undefined ? formatNumber(orient.yaw, 1) : '--';
  const pitch = orient?.pitch !== null && orient?.pitch !== undefined ? formatNumber(orient.pitch, 1) : '--';
  const roll = orient?.roll !== null && orient?.roll !== undefined ? formatNumber(orient.roll, 1) : '--';

  return (
    <main className="flex-1 p-4 lg:p-6 max-w-[1800px] w-full mx-auto flex flex-col gap-5">
      {/* Avionic Status Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0E1524] border border-slate-800/90 p-3.5 rounded-2xl shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-extrabold uppercase tracking-wider text-slate-100">
              Avionics & Marine Instrumentation
            </h2>
            <span className="text-[10px] font-mono font-bold text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-2 py-0.5 rounded">
              BNO055 9-DOF
            </span>
          </div>
        </div>

        {/* Quick Readout Strip */}
        <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800">
            <span className="text-slate-400">HDG:</span>
            <strong className="text-cyan-300">{heading}°</strong>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800">
            <span className="text-slate-400">PITCH:</span>
            <strong className="text-slate-200">{pitch}°</strong>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800">
            <span className="text-slate-400">ROLL:</span>
            <strong className="text-slate-200">{roll}°</strong>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800">
            <span className="text-slate-400">IMU LINK:</span>
            <span className={isConnected ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
              {isConnected ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      {/* Primary Flight / Marine Display Cluster: 3 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Instrument 1: Attitude Indicator (Artificial Horizon) */}
        <AttitudeIndicator imu={imu} />

        {/* Instrument 2: Digital Compass Rose */}
        <CompassHeadingIndicator imu={imu} gps={gps} />

        {/* Instrument 3: 3D Vessel Attitude Model */}
        <ASVOrientation3D imu={imu} />
      </div>

      {/* Secondary Dynamics Cluster: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Instrument 4: Inertial Accelerometers (Linear, Raw, Gravity) */}
        <InertialGauges imu={imu} />

        {/* Instrument 5: Gyroscope & Rate of Turn (ROT) */}
        <GyroscopeGauge imu={imu} />
      </div>

      {/* Vertical Status & Health Diagnostics: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Instrument 6: GNSS Vertical Altitude (5 Columns) */}
        <div className="lg:col-span-5">
          <AltitudeGauge gps={gps} />
        </div>

        {/* Instrument 7: Sensor Health & Calibration (7 Columns) */}
        <div className="lg:col-span-7">
          <IMUCalibrationStatusPanel imu={imu} />
        </div>
      </div>
    </main>
  );
}
