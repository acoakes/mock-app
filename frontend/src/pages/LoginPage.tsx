import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Banner, Button, TextField } from '@arc';
import { useLoginMutation } from '../api/apiSlice';
import { useAppDispatch } from '../store/hooks';
import { setAuthenticated } from '../features/auth/authSlice';
import { TESTIDS } from '../testids';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useAppDispatch();
  const [login] = useLoginMutation();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const res = await login({ username, password }).unwrap();
      if (res.authenticated && res.user) {
        dispatch(setAuthenticated(res.user));
        // login invalidatesTags:['Session'], which refetches the root-mounted
        // getSession in App.tsx, picking up mode/refresh_seconds — no explicit
        // refetch needed here.
        // Navigate to the originally-requested route (preserved by RequireAuth
        // in location.state.from) or the /dashboard default. The /dashboard
        // default is a HARD contract: login_page.py::login() waits for
        // **/dashboard**, so a bare login (no `from`) MUST land on /dashboard.
        const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
        const dest = from && from !== '/login' ? from : '/dashboard';
        navigate(dest, { replace: true });
        return;
      }
      setError('Invalid credentials');
    } catch {
      setError('Invalid credentials');
    }
  };

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <h1 className="login-title">Data Analytics Platform</h1>
        <h2 className="login-subtitle">Sign In</h2>
        {/* login-form; inputs are native name="username"/"password" (load-bearing). */}
        <form data-testid={TESTIDS.loginForm} onSubmit={handleSubmit}>
          <TextField
            name="username"
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter username"
            autoComplete="username"
            testid={TESTIDS.usernameInput}
          />
          <TextField
            name="password"
            type="password"
            label="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter password"
            autoComplete="current-password"
            testid={TESTIDS.passwordInput}
          />
          {error ? (
            <Banner variant="error" testid={TESTIDS.errorMessage}>
              {error}
            </Banner>
          ) : null}
          <Button type="submit" variant="primary" className="btn-block" testid={TESTIDS.loginButton}>
            Login
          </Button>
        </form>
      </div>
    </div>
  );
}
