import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export type AuthStatus = 'unknown' | 'authenticated' | 'anonymous';

export interface AuthState {
  user: string | null;
  status: AuthStatus;
}

const initialState: AuthState = {
  user: null,
  status: 'unknown',
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setAuthenticated(state, action: PayloadAction<string>) {
      state.user = action.payload;
      state.status = 'authenticated';
    },
    setAnonymous(state) {
      state.user = null;
      state.status = 'anonymous';
    },
    setUnknown(state) {
      state.user = null;
      state.status = 'unknown';
    },
  },
});

export const { setAuthenticated, setAnonymous, setUnknown } = authSlice.actions;
export default authSlice.reducer;
