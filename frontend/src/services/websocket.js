function resolveWsUrl() {
  const fromEnv = import.meta.env.VITE_WS_URL;
  if (fromEnv && String(fromEnv).trim()) {
    return String(fromEnv).trim();
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  if (import.meta.env.DEV) {
    return `${protocol}//${window.location.hostname}:8000/ws/telemetry`;
  }
  return `${protocol}//${window.location.host}/ws/telemetry`;
}

class TelemetryWebSocket {
  constructor() {
    this.socket = null;
    this.listeners = new Set();
    this.statusListeners = new Set();
    this.reconnectTimer = null;
    this.connected = false;
  }

  connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const url = resolveWsUrl();

    try {
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        this.connected = true;
        this.notifyStatus(true);
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.notify(data);
        } catch (err) {
          console.error("Failed to parse telemetry message:", err);
        }
      };

      this.socket.onclose = () => {
        this.connected = false;
        this.notifyStatus(false);
        this.scheduleReconnect();
      };

      this.socket.onerror = () => {
        this.connected = false;
        this.notifyStatus(false);
      };
    } catch (e) {
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 1500);
    }
  }

  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  subscribeStatus(callback) {
    this.statusListeners.add(callback);
    callback(this.connected);
    return () => this.statusListeners.delete(callback);
  }

  notify(data) {
    this.listeners.forEach(cb => cb(data));
  }

  notifyStatus(status) {
    this.statusListeners.forEach(cb => cb(status));
  }
}

export const telemetryWS = new TelemetryWebSocket();
