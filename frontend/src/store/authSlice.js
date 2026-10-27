/**
 * authSlice.js - Who is logged in.
 * The token is kept in sessionStorage: it disappears when the browser tab is closed,
 * which is safer on a shared police-station computer than localStorage.
 */
import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import api from '../services/api';

export const login = createAsyncThunk('auth/login', async ({ email, password }, { rejectWithValue }) => {
  try {
    const res = await api.post('/auth/login', { email, password });
    return res.data;
  } catch (e) {
    return rejectWithValue(e.message);
  }
});

const saved = JSON.parse(sessionStorage.getItem('rg_user') || 'null');

const authSlice = createSlice({
  name: 'auth',
  initialState: { user: saved, token: sessionStorage.getItem('rg_token'), loading: false, error: null },
  reducers: {
    logout(state) {
      sessionStorage.clear();
      state.user = null;
      state.token = null;
    },
    clearError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(login.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(login.fulfilled, (state, action) => {
        state.loading = false;
        state.user = action.payload.user;
        state.token = action.payload.access_token;
        sessionStorage.setItem('rg_token', action.payload.access_token);
        sessionStorage.setItem('rg_user', JSON.stringify(action.payload.user));
      })
      .addCase(login.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload || 'Login failed';
      });
  },
});

export const { logout, clearError } = authSlice.actions;
export default authSlice.reducer;
