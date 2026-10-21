import { isRejectedWithValue, type Middleware } from '@reduxjs/toolkit';
import { setAnonymous } from './authSlice';
import type { RootState } from '../../store';

// Global RTK Query error handler (design §6): any 401 from a DATA endpoint maps
// auth.status back to 'anonymous'. Redirect to /login is then driven
// declaratively by <RequireAuth> reacting to the status flip — no imperative
// navigate from middleware, so there is a single redirect path.
//
// Robustness note for the session-cookie flow: unauthenticated data endpoints
// 302 -> /login server-side, and fetch transparently follows redirects, so a
// raw 401 is not guaranteed on every expiry. GET /api/session is the
// authoritative signal (it returns 401 JSON rather than redirecting) and is
// mounted at the app root, so an expiry surfaces here on the next session read;
// this middleware additionally catches any explicit 401 the moment it appears.
//
// login's own 401 is the invalid-credentials path handled inline by LoginPage,
// so it is excluded here.
export const authErrorMiddleware: Middleware =
  (apiMw) => (next) => (action) => {
    if (isRejectedWithValue(action)) {
      const payload = action.payload as { status?: number } | undefined;
      const endpointName = (action.meta as { arg?: { endpointName?: string } } | undefined)?.arg
        ?.endpointName;
      if (payload?.status === 401 && endpointName !== 'login') {
        const state = apiMw.getState() as RootState;
        if (state.auth.status !== 'anonymous') {
          apiMw.dispatch(setAnonymous());
        }
      }
    }
    return next(action);
  };
