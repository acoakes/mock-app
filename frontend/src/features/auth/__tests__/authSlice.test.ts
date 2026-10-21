import { describe, expect, it } from 'vitest';
import authReducer, {
  setAuthenticated,
  setAnonymous,
  setUnknown,
  type AuthState,
} from '../authSlice';

describe('authSlice', () => {
  it('starts anonymous-unknown with no user', () => {
    const state = authReducer(undefined, { type: '@@INIT' });
    expect(state).toEqual<AuthState>({ user: null, status: 'unknown' });
  });

  it('setAuthenticated sets the user and status=authenticated', () => {
    const state = authReducer(undefined, setAuthenticated('demo'));
    expect(state).toEqual<AuthState>({ user: 'demo', status: 'authenticated' });
  });

  it('setAnonymous clears the user and status=anonymous', () => {
    const authed: AuthState = { user: 'demo', status: 'authenticated' };
    const state = authReducer(authed, setAnonymous());
    expect(state).toEqual<AuthState>({ user: null, status: 'anonymous' });
  });

  it('setUnknown clears the user and status=unknown', () => {
    const authed: AuthState = { user: 'demo', status: 'authenticated' };
    const state = authReducer(authed, setUnknown());
    expect(state).toEqual<AuthState>({ user: null, status: 'unknown' });
  });
});
