import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import basicSsl from '@vitejs/plugin-basic-ssl';

// `npm run dev -- --host` serves over HTTPS with a self-signed certificate,
// because `navigator.geolocation` only works on a secure origin and the phone
// has to reach the laptop by IP (SPEC §8.7).
const useHttps = process.argv.includes('--host');

export default defineConfig({
  plugins: [react(), ...(useHttps ? [basicSsl()] : [])],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/media': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    // MapLibre and turf are big and only a couple of screens need them, so
    // they get their own chunks the rest of the app never downloads
    // (SPEC §15). Vite still defaults to a <link rel="modulepreload"> for a
    // dynamically-imported chunk if it's reachable from the entry module
    // graph -- that hint is shared across every route via the single
    // index.html, so Nearby (which never touches turf) was paying for it on
    // every load. Drop the two lazy chunks from the preload list.
    modulePreload: {
      resolveDependencies: (_url, deps) =>
        deps.filter((dep) => !dep.includes('/maplibre-') && !dep.includes('/turf-')),
    },
    rollupOptions: {
      output: {
        manualChunks: {
          maplibre: ['maplibre-gl'],
          turf: ['@turf/turf'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    // Unit tests live beside the code; e2e/ belongs to Playwright, which has
    // its own runner and its own `test` export.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});
