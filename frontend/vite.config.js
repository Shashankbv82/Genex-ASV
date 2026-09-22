import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Bind to all interfaces so the Vite UI is reachable on localhost and over
// private Tailscale/LAN IPs. Do not expose this port on the public internet.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    watch: {
      usePolling: true,
      interval: 1000,
      ignored: ['**/node_modules/**', '**/dist/**']
    },
    fs: {
      strict: true,
      allow: ['.']
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
  },
});
