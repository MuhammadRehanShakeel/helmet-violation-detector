/**
 * notificationsSlice.js - The bell icon: the last 50 live events and how many are unread.
 * `tick` goes up on every new violation, so pages can refresh themselves.
 */
import { createSlice } from '@reduxjs/toolkit';

const slice = createSlice({
  name: 'notifications',
  initialState: { items: [], unread: 0, tick: 0, connection: 'offline' },
  reducers: {
    received(state, action) {
      const e = action.payload;
      if (['violation', 'appeal', 'access_request', 'stream', 'payment'].includes(e.type)) {
        state.items.unshift({ ...e, at: new Date().toISOString(), id: `${Date.now()}-${Math.random()}` });
        state.items = state.items.slice(0, 50);
        state.unread += 1;
      }
      if (e.type === 'violation' || e.type === 'appeal' || e.type === 'payment') state.tick += 1;
    },
    markRead(state) {
      state.unread = 0;
    },
    setConnection(state, action) {
      state.connection = action.payload;
    },
  },
});

export const { received, markRead, setConnection } = slice.actions;
export default slice.reducer;
