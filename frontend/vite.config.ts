/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev single-origin setup (design §6): proxy /api -> Flask on :5000 so the
// session cookie "just works" without cross-origin CORS. The build itself is
// origin-agnostic (the api slice reads VITE_API_BASE_URL ?? '/api').
export default defineConfig({
  base: '/',
  plugins: [react()],
  resolve: {
    alias: {
      '@arc': fileURLToPath(new URL('./src/components/arc', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      // WebSocket live-push channel (design §3). `ws: true` upgrades the proxy
      // so the SPA's single-origin `new WebSocket('/ws')` reaches Flask in dev.
      '/ws': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
