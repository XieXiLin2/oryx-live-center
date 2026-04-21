import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, the FastAPI backend listens on :8000 and proxies media to SRS.
// In production, Nginx is the front door; see deploy/nginx/nginx.conf.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      // FLV via FastAPI's reverse proxy (dev only).
      '/live': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // WebRTC WHIP/WHEP signaling via FastAPI's reverse proxy.
      '/rtc': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
