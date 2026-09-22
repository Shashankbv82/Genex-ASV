export function formatCoordinate(val, isLat) {
  if (val === null || val === undefined || isNaN(Number(val))) return '--.------°';
  const num = Number(val);
  const dir = isLat ? (num >= 0 ? 'N' : 'S') : (num >= 0 ? 'E' : 'W');
  const absVal = Math.abs(num);
  return absVal.toFixed(6) + '° ' + dir;
}

export function formatSpeed(mps) {
  if (mps === null || mps === undefined || isNaN(Number(mps))) return '-- m/s';
  const num = Number(mps);
  const kmh = (num * 3.6).toFixed(1);
  return num.toFixed(1) + ' m/s (' + kmh + ' km/h)';
}

export function formatCourse(deg) {
  if (deg === null || deg === undefined || isNaN(Number(deg))) return '--°';
  return Number(deg).toFixed(1) + '°';
}

export function formatAge(seconds) {
  if (seconds === null || seconds === undefined || isNaN(Number(seconds)) || seconds > 300) return 'Lost';
  const sec = Number(seconds);
  if (sec < 1.0) return Math.round(sec * 1000) + 'ms ago';
  return sec.toFixed(1) + 's ago';
}

export function formatLastKnownAge(seconds) {
  if (seconds === null || seconds === undefined || isNaN(Number(seconds))) return 'Recent';
  const s = Math.max(0, Math.round(Number(seconds)));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}h ${remM}m ago`;
}

export function formatNumber(val, decimals = 2, fallback = '--') {
  if (val === null || val === undefined || isNaN(Number(val))) return fallback;
  return Number(val).toFixed(decimals);
}

export function getFixQualityLabel(quality) {
  switch (quality) {
    case 1: return 'Autonomous 3D Fix';
    case 2: return 'DGPS Fix';
    case 4: return 'RTK Fixed';
    case 5: return 'RTK Float';
    case 6: return 'Dead Reckoning';
    default: return 'No Valid Fix';
  }
}

export function getSatelliteMarkerColor(count) {
  if (count === null || count === undefined || isNaN(Number(count)) || Number(count) <= 1) return '#EF4444'; // RED (0 or 1 satellite)
  if (Number(count) === 2) return '#F59E0B'; // YELLOW (exactly 2 satellites)
  return '#10B981'; // GREEN (> 2 satellites)
}
