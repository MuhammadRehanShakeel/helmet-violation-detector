import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The browser only talks to http://localhost:5174.
// Vite forwards /api/* to the FastAPI backend on port 5001, so there are
// no cross-site (CORS) problems. 5174/5001 = never clashes with the FYP (5173/5000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: { chunkSizeWarningLimit: 1500 },
});
