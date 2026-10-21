import { configureStore } from '@reduxjs/toolkit';
import { api } from '../api/apiSlice';
import authReducer from '../features/auth/authSlice';
import uiReducer from '../features/ui/uiSlice';
import { authErrorMiddleware } from '../features/auth/authErrorMiddleware';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    ui: uiReducer,
    [api.reducerPath]: api.reducer,
  },
  // authErrorMiddleware runs AFTER api.middleware so RTK Query has produced the
  // rejected action it inspects (global 401 -> anonymous, design §6).
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(api.middleware, authErrorMiddleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
