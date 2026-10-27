/**
 * events.js - Live notifications from the backend (Server-Sent Events).
 *
 * We read GET /api/events with fetch() instead of EventSource, because fetch can send the login
 * token in the Authorization header (EventSource would need it in the URL, where it can leak into logs).
 * If the connection drops (backend restarted, Wi-Fi hiccup) we reconnect after 2, 4, 8 ... 30 seconds.
 */
import { API_URL } from './api';

const listeners = new Set();
let controller = null;

export function onEvent(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function startEvents(onStatus) {
  stopEvents();
  controller = new AbortController();
  const { signal } = controller;
  let wait = 2000;

  const run = async () => {
    while (!signal.aborted) {
      try {
        const token = sessionStorage.getItem('rg_token');
        if (!token) return;
        const res = await fetch(`${API_URL}/events`, { headers: { Authorization: `Bearer ${token}` }, signal });
        if (res.status === 401 || res.status === 403) return;          // logged out: stop trying
        if (!res.ok || !res.body) throw new Error(`events ${res.status}`);
        onStatus?.('connected');
        wait = 2000;
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let cut;
          while ((cut = buffer.indexOf('\n\n')) >= 0) {
            const block = buffer.slice(0, cut);
            buffer = buffer.slice(cut + 2);
            const data = block.split('\n').filter((l) => l.startsWith('data: ')).map((l) => l.slice(6)).join('');
            if (!data || data === '{}') continue;
            try {
              const event = JSON.parse(data);
              listeners.forEach((fn) => fn(event));
            } catch { /* ignore broken lines */ }
          }
        }
      } catch (e) {
        if (signal.aborted) return;
      }
      onStatus?.('reconnecting');
      await new Promise((r) => setTimeout(r, wait));
      wait = Math.min(30000, wait * 2);
    }
  };
  run();
}

export function stopEvents() {
  controller?.abort();
  controller = null;
}
