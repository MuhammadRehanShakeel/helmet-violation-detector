/**
 * jobsSlice.js - Uploaded photos/videos and their analysis progress.
 */
import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import api from '../services/api';

export const fetchJobs = createAsyncThunk('jobs/fetch', async () => (await api.get('/jobs')).data);

export const uploadMedia = createAsyncThunk(
  'jobs/upload',
  async ({ file, cameraId, onProgress }, { rejectWithValue }) => {
    const form = new FormData();
    form.append('file', file);
    if (cameraId) form.append('camera_id', cameraId);
    try {
      const res = await api.post('/jobs', form, {
        onUploadProgress: (e) => onProgress?.(Math.round((e.loaded * 100) / (e.total || 1))),
      });
      return res.data;
    } catch (e) {
      return rejectWithValue(e.message);
    }
  }
);

const jobsSlice = createSlice({
  name: 'jobs',
  initialState: { items: [], loading: false },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchJobs.pending, (state) => {
        state.loading = state.items.length === 0;
      })
      .addCase(fetchJobs.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload;
      })
      .addCase(fetchJobs.rejected, (state) => {
        state.loading = false;
      });
  },
});

export default jobsSlice.reducer;
