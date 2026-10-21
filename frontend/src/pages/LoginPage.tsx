import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Banner, Button, TextField } from '@arc';
import { useLoginMutation } from '../api/apiSlice';
import { useAppDispatch } from '../store/hooks';
import { setAuthenticated } from '../features/auth/authSlice';
import { TESTIDS } from '../testids';

export default function LoginPage() {
  const navigate = useNavigate();
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
        // HARD contract: login_page.py::login() waits for **/dashboard**.
        navigate('/dashboard');
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
