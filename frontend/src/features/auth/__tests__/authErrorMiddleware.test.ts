import { describe, expect, it } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setAuthenticated } from '../authSlice';
import { authErrorMiddleware } from '../authErrorMiddleware';

// Build a tiny store with just the auth reducer + the middleware under test.
function makeStore() {
  return configureStore({
    reducer: { auth: authReducer },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(authErrorMiddleware),
  });
}

// A rejected-with-value action shaped exactly like what RTK Query emits:
// type ends with '/rejected', meta.rejectedWithValue === true, meta.arg carries
// the endpointName, payload carries the HTTP status.
function rejectedWithValue(endpointName: string, status: number) {
  return {
    type: 'api/executeQuery/rejected',
    payload: { status },
    error: { message: 'Rejected' },
    meta: {
      rejectedWithValue: true,
      requestStatus: 'rejected' as const,
      requestId: 'x',
      arg: { endpointName },
      aborted: false,
      condition: false,
    },
  };
}

describe('authErrorMiddleware', () => {
  it('flips status to anonymous on a 401 from a non-login data endpoint', () => {
    const store = makeStore();
    store.dispatch(setAuthenticated('demo'));
    expect(store.getState().auth.status).toBe('authenticated');

    store.dispatch(rejectedWithValue('getDashboard', 401));

    expect(store.getState().auth.status).toBe('anonymous');
    expect(store.getState().auth.user).toBeNull();
  });

  it('does NOT flip status on a 401 from the login endpoint (invalid-creds path)', () => {
    const store = makeStore();
    store.dispatch(setAuthenticated('demo'));

    store.dispatch(rejectedWithValue('login', 401));

    expect(store.getState().auth.status).toBe('authenticated');
    expect(store.getState().auth.user).toBe('demo');
  });

  it('does NOT flip status on a non-401 rejection', () => {
    const store = makeStore();
    store.dispatch(setAuthenticated('demo'));

    store.dispatch(rejectedWithValue('getDashboard', 500));

    expect(store.getState().auth.status).toBe('authenticated');
  });
});
