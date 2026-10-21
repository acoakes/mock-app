import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import { api } from '../../../api/apiSlice';
import authReducer from '../authSlice';
import uiReducer from '../../ui/uiSlice';
import { authErrorMiddleware } from '../authErrorMiddleware';

// Mock the login mutation hook so the test exercises LoginPage's DOM + flow
// logic without the fetch/AbortSignal plumbing (jsdom's fetch rejects the
// AbortSignal RTK Query passes). unwrap() is what LoginPage awaits.
const loginMock = vi.fn();
vi.mock('../../../api/apiSlice', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../../../api/apiSlice')>();
  return {
    ...mod,
    useLoginMutation: () => [
      (arg: { username: string; password: string }) => ({
        unwrap: () => loginMock(arg),
      }),
      {},
    ],
  };
});

import LoginPage from '../../../pages/LoginPage';

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ui: uiReducer, [api.reducerPath]: api.reducer },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().concat(api.middleware, authErrorMiddleware),
  });
}

function renderLogin() {
  const store = makeStore();
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

describe('LoginPage DOM contracts + flow', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the load-bearing DOM: login-form, name inputs, submit button', () => {
    renderLogin();
    expect(screen.getByTestId('login-form').tagName).toBe('FORM');

    const username = document.querySelector('input[name="username"]');
    const password = document.querySelector('input[name="password"]');
    expect(username).toBeInTheDocument();
    expect(password).toBeInTheDocument();

    const submit = document.querySelector('button[type="submit"]');
    expect(submit).toBeInTheDocument();
    expect(screen.getByTestId('login-form').contains(submit)).toBe(true);
  });

  it('shows the error-message banner when login rejects (401 path)', async () => {
    loginMock.mockRejectedValue({ status: 401, data: { authenticated: false } });
    renderLogin();

    fireEvent.click(document.querySelector('button[type="submit"]')!);

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument();
    });
  });

  it('authenticates and shows no error when login resolves (200 path)', async () => {
    loginMock.mockResolvedValue({ authenticated: true, user: 'demo' });
    const store = renderLogin();

    fireEvent.change(document.querySelector('input[name="username"]')!, {
      target: { value: 'demo' },
    });
    fireEvent.change(document.querySelector('input[name="password"]')!, {
      target: { value: 'demo' },
    });
    fireEvent.click(document.querySelector('button[type="submit"]')!);

    await waitFor(() => {
      expect(store.getState().auth.status).toBe('authenticated');
    });
    expect(store.getState().auth.user).toBe('demo');
    expect(screen.queryByTestId('error-message')).not.toBeInTheDocument();
  });
});
