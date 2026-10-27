import { configureStore } from '@reduxjs/toolkit';
import auth from './authSlice';
import jobs from './jobsSlice';
import notifications from './notificationsSlice';
import violations from './violationsSlice';

export const store = configureStore({ reducer: { auth, jobs, violations, notifications } });
