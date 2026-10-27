import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The browser only talks to http://localhost:5174.
// Vite forwards /api/* to the FastAPI backend on port 5001, so there are
// no cross-site (CORS) problems. 5174/5001 = never clashes with the FYP (5173/5000).
//
// PHONE=1 (start_phone_camera.bat): serve over HTTPS on the Wi-Fi network.
// Phone browsers only allow the camera on HTTPS pages, so this is needed to use a
// phone as the live traffic camera. The backend itself stays private on the laptop.
const phone = process.env.PHONE === '1';

export default defineConfig(async () => ({
  // the HTTPS helper is only loaded in phone mode, so normal mode never needs it
  plugins: [react(), ...(phone ? [(await import('@vitejs/plugin-basic-ssl')).default()] : [])],
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
}));
