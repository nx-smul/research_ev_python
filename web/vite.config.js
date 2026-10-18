import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: process.env.GITHUB_ACTIONS ? '/research_ev_python/' : '/',
  plugins: [react()],
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'maplibre-vendor': ['maplibre-gl'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/testSetup.js',
  },
});
