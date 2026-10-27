/**
 * violationsSlice.js - The review queue: list, filters and paging.
 * Filters live in Redux so they are kept when you open a violation and come back.
 */
import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import api from '../services/api';

export const fetchViolations = createAsyncThunk('violations/fetch', async (_, { getState, rejectWithValue }) => {
  const { filters, page } = getState().violations;
  const params = { page, page_size: 24 };
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined && v !== false) params[k] = v;
  });
  try {
    return (await api.get('/violations', { params })).data;
  } catch (e) {
    return rejectWithValue(e.message);
  }
});

const violationsSlice = createSlice({
  name: 'violations',
  initialState: {
    items: [],
    total: 0,
    page: 1,
    loading: false,
    error: null,
    filters: { status: 'pending', violation_type: '', camera_id: '', plate: '', job_id: '', low_confidence: false },
  },
  reducers: {
    setFilter(state, action) {
      state.filters = { ...state.filters, ...action.payload };
      state.page = 1;
    },
    setPage(state, action) {
      state.page = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchViolations.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchViolations.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload.items;
        state.total = action.payload.total;
      })
      .addCase(fetchViolations.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      });
  },
});

export const { setFilter, setPage } = violationsSlice.actions;
export default violationsSlice.reducer;
