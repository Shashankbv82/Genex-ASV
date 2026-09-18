import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import { createASVMarkerElement } from './ASVMarker';
import { MapBottomBar } from './MapBottomBar';
import { Locate, Layers, AlertTriangle, MapPinOff, Activity, Compass } from 'lucide-react';

const SATELLITE_TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

export function LiveMap({ gps, filtered, imu }) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  
  const [mapError, setMapError] = useState(null);
  const [lastValidPos, setLastValidPos] = useState(null);
  const [followVehicle, setFollowVehicle] = useState(true);

  // Initialize MapLibre with overzoom configuration
  useEffect(() => {
    if (!mapContainerRef.current) return;

    try {
      const initialCenter = [77.6207, 12.9355];

      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: {
          version: 8,
          sources: {
            'satellite-tiles': {
              type: 'raster',
              tiles: [SATELLITE_TILE_URL],
              tileSize: 256,
              minzoom: 0,
              maxzoom: 19,
              attribution: 'Esri, Maxar, Earthstar Geographics'
            }
          },
          layers: [
            {
              id: 'satellite-layer',
              type: 'raster',
              source: 'satellite-tiles',
              minzoom: 0,
              maxzoom: 24
            }
          ]
        },
        center: initialCenter,
        zoom: 17,
        maxZoom: 22,
        minZoom: 2,
        pitch: 0,
        bearing: 0,
        attributionControl: false
      });

      map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');
      mapRef.current = map;

      return () => {
        try {
          map.remove();
        } catch (e) {
          // Ignore unmount cleanup error
        }
      };
    } catch (err) {
      console.error('Failed to initialize MapLibre GL:', err);
      setMapError('MapLibre failed to initialize: ' + (err?.message || String(err)));
    }
  }, []);

  // Update marker position and appearance
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Use filtered coordinates if filter is active and valid, otherwise fallback to raw GPS
    const isFilteredActive = Boolean(filtered?.is_filtered && filtered?.latitude != null && filtered?.longitude != null);
    const targetLat = isFilteredActive ? filtered.latitude : gps?.latitude;
    const targetLon = isFilteredActive ? filtered.longitude : gps?.longitude;
    const satCount = gps?.satellites_used ?? 0;
    
    // Strict coordinate validation: reject null, undefined, NaN, and 0,0 (Null Island)
    const isValidCoordinate = (
      targetLat !== null && targetLat !== undefined && !isNaN(targetLat) &&
      targetLon !== null && targetLon !== undefined && !isNaN(targetLon) &&
      !(Math.abs(targetLat) < 0.0001 && Math.abs(targetLon) < 0.0001) &&
      targetLat >= -90 && targetLat <= 90 && targetLon >= -180 && targetLon <= 180
    );

    const hasLiveFix = isValidCoordinate && gps?.fix_valid && !gps?.is_stale;

    // Heading priority: 1) IMU verified fused heading (+X forward), 2) Filtered GPS velocity course, 3) Raw GPS course
    const imuHeadingValid = Boolean(imu?.orientation?.heading_valid && imu?.orientation?.yaw !== undefined && !imu?.is_stale);
    const heading = imuHeadingValid 
      ? imu.orientation.yaw 
      : ((filtered?.course_deg != null) ? filtered.course_deg : (gps?.course_deg ?? null));

    const ensureMarker = (coords, colorSatCount, rotation, isImuHeading) => {
      try {
        if (!markerRef.current) {
          const markerEl = createASVMarkerElement(colorSatCount, isImuHeading);
          markerRef.current = new maplibregl.Marker({
            element: markerEl,
            rotationAlignment: 'map'
          })
            .setLngLat(coords)
            .addTo(map);

          if (rotation !== null && !isNaN(rotation)) {
            markerRef.current.setRotation(rotation);
          }
          return;
        }

        markerRef.current.setLngLat(coords);
        if (rotation !== null && !isNaN(rotation)) {
          markerRef.current.setRotation(rotation);
        }

        const host = markerRef.current.getElement();
        if (host) {
          const refreshed = createASVMarkerElement(colorSatCount, isImuHeading);
          host.replaceChildren(...refreshed.childNodes);
          host.className = refreshed.className;
        }
      } catch (markerErr) {
        console.warn('Error updating ASV marker:', markerErr);
      }
    };

    if (hasLiveFix) {
      const coords = [targetLon, targetLat];
      setLastValidPos(coords);
      ensureMarker(coords, satCount, heading, imuHeadingValid);
      if (followVehicle) {
        try {
          map.easeTo({ center: coords, duration: 400 });
        } catch (e) {}
      }
    } else if (lastValidPos && markerRef.current) {
      // Retain last known position with 0 satellites (red) indicating stale/lost fix
      ensureMarker(lastValidPos, 0, heading, imuHeadingValid);
    }
  }, [
    filtered?.is_filtered,
    filtered?.latitude,
    filtered?.longitude,
    filtered?.course_deg,
    gps?.latitude,
    gps?.longitude,
    gps?.course_deg,
    gps?.satellites_used,
    gps?.fix_valid,
    gps?.is_stale,
    imu?.orientation?.yaw,
    imu?.orientation?.heading_valid,
    imu?.is_stale,
    followVehicle,
    lastValidPos
  ]);


  const handleRecenter = () => {
    if (!mapRef.current) return;
    if (lastValidPos) {
      mapRef.current.flyTo({ center: lastValidPos, zoom: 19, duration: 1000 });
      setFollowVehicle(true);
    }
  };

  const isFiltered = Boolean(filtered?.is_filtered);
  const filterMode = filtered?.diagnostics?.filter_mode || 'disabled';
  const isCoasting = Boolean(filtered?.uncertainty_warning);

  return (
    <div className="relative w-full h-full min-h-[420px] rounded-xl overflow-hidden border border-slate-800 shadow-2xl bg-[#090D16]">
      {mapError ? (
        <div className="w-full h-full min-h-[420px] flex flex-col items-center justify-center p-6 text-center bg-[#070B14]">
          <MapPinOff className="w-12 h-12 text-amber-400/80 mb-3" />
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Map Display Unavailable</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-md font-mono">{mapError}</p>
        </div>
      ) : (
        <div ref={mapContainerRef} className="w-full h-full min-h-[420px]" />
      )}

      {/* Top Map Action Bar */}
      <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-2">
        <button
          onClick={handleRecenter}
          disabled={!lastValidPos}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border shadow-lg backdrop-blur-md transition-all ${
            followVehicle && lastValidPos
              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' 
              : 'bg-slate-900/80 text-slate-300 border-slate-700 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed'
          }`}
          title="Recenter and follow ASV"
        >
          <Locate className="w-3.5 h-3.5" />
          <span>{followVehicle && lastValidPos ? 'Tracking ASV' : 'Recenter'}</span>
        </button>

        <div className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-mono bg-slate-950/80 text-slate-300 border border-slate-800 backdrop-blur-md">
          <Layers className="w-3.5 h-3.5 text-cyan-400" />
          <span>Esri Satellite</span>
        </div>

        {/* Kalman Filter State Badge */}
        {isFiltered ? (
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium border backdrop-blur-md transition-all ${
              isCoasting
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse'
                : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
            }`}
            title={`Kalman Filter: ${filterMode}. Disp: ${filtered?.diagnostics?.displacement_m ?? 0}m`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>
              {isCoasting ? `KF Coasting (${filterMode})` : `KF 5Hz (${filterMode})`}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono text-slate-400 bg-slate-950/80 border border-slate-800 backdrop-blur-md">
            <span>Raw GNSS (1Hz)</span>
          </div>
        )}

        {/* IMU Attitude / Heading Badge */}
        {imu?.connected ? (
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium border backdrop-blur-md transition-all ${
              imu.orientation?.heading_valid
                ? 'bg-sky-500/20 text-sky-300 border-sky-500/40'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse'
            }`}
            title={`BNO055 IMU: Heading ${imu.orientation?.yaw?.toFixed(1) ?? '--'}°, Roll ${imu.orientation?.roll?.toFixed(1) ?? '--'}°, Pitch ${imu.orientation?.pitch?.toFixed(1) ?? '--'}°. Calib: S${imu.calibration?.sys} G${imu.calibration?.gyro} A${imu.calibration?.accel} M${imu.calibration?.mag}`}
          >
            <Compass className="w-3.5 h-3.5" />
            <span>
              {imu.orientation?.heading_valid 
                ? `HDG: ${imu.orientation.yaw.toFixed(1)}°` 
                : `IMU Calib (G:${imu.calibration?.gyro}/3)`}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono text-slate-500 bg-slate-950/80 border border-slate-800 backdrop-blur-md">
            <Compass className="w-3.5 h-3.5" />
            <span>IMU Offline</span>
          </div>
        )}


        {gps?.is_stale && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/40 backdrop-blur-md animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>GPS Stale — {lastValidPos ? 'Showing Last Position' : 'No Fix Yet'}</span>
          </div>
        )}
      </div>

      {/* Bottom Information Overlay */}
      <MapBottomBar gps={gps || {}} />
    </div>
  );
}
