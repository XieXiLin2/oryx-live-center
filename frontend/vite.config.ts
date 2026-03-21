import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      // Oryx media streams (FLV, HLS, TS) reverse proxy in dev
      '/live': {
        target: 'http://localhost:2022',
        changeOrigin: true,
      },
      // Oryx WebRTC signaling (WHIP/WHEP) proxy in dev
      '/rtc': {
        target: 'http://localhost:2022',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
