import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Used when the UI is connected to the Spring Boot API-service:
    // every request to /api/... is forwarded to http://localhost:8080/api/...
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/auth': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/jobs': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
});
