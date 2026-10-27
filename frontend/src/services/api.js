/**
 * api.js - Every call from the React app to the RoadGuard backend goes through here.
 *
 * - Browser: requests go to /api/... and Vite forwards them to the backend (vite.config.js).
 * - Android app (Capacitor): set VITE_API_URL in frontend/.env to the PC's Wi-Fi address.
 * - The login token is added to every request automatically.
 * - 401 (expired or invalid login) -> clear the session and go to the login page.
 */
import axios from 'axios';

const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

const api = axios.create({ baseURL: API_URL, timeout: 15 * 60 * 1000 });

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('rg_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    if (status === 401 && !error.config?.url?.includes('/auth/login')) {
      sessionStorage.clear();
      if (!window.location.pathname.startsWith('/login')) window.location.href = '/login';
    }
    if (typeof detail === 'string') error.message = detail;
    else if (Array.isArray(detail)) error.message = detail.map((d) => d.msg).join(', ');
    return Promise.reject(error);
  }
);

/**
 * Evidence photos are private, so a plain <img src> cannot load them (no token).
 * We download them with the token and turn them into a temporary local URL.
 */
const imageCache = new Map();
export async function loadPrivateImage(path) {
  if (imageCache.has(path)) return imageCache.get(path);
  const res = await api.get(path, { responseType: 'blob' });
  const url = URL.createObjectURL(res.data);
  imageCache.set(path, url);
  return url;
}

export async function downloadFile(path, filename) {
  const res = await api.get(path, { responseType: 'blob' });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export { API_URL };
export default api;
