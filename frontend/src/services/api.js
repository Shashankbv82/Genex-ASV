import axios from 'axios';

function resolveApiBase() {
  const fromEnv = import.meta.env.VITE_API_BASE_URL;
  if (fromEnv && String(fromEnv).trim()) {
    return String(fromEnv).replace(/\/$/, '');
  }

  // Dev UI on Vite: talk to backend on same host, port 8000.
  // Production (served by FastAPI from /frontend/dist): same-origin /api.
  if (import.meta.env.DEV) {
    return `http://${window.location.hostname}:8000/api`;
  }
  return '/api';
}

export const api = axios.create({
  baseURL: resolveApiBase(),
  timeout: 3000,
});

export const getGPS = async () => {
  const res = await api.get('/gps');
  return res.data;
};

export const getTelemetry = async () => {
  const res = await api.get('/telemetry');
  return res.data;
};

export const getHealth = async () => {
  const res = await api.get('/health');
  return res.data;
};

export const setOperatingMode = async (mode) => {
  const res = await api.post('/mode', { mode });
  return res.data;
};
