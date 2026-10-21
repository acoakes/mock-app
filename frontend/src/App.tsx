import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell, type NavLinkItem } from '@arc';
import { useGetSessionQuery } from './api/apiSlice';
import { useAppDispatch, useAppSelector } from './store/hooks';
import { setAnonymous, setAuthenticated } from './features/auth/authSlice';
import { useLogout } from './features/auth/useLogout';
import { RequireAuth } from './features/auth/RequireAuth';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AnomaliesPage from './pages/AnomaliesPage';
import AnomalyDetailPage from './pages/AnomalyDetailPage';
import RcaPage from './pages/RcaPage';
import RcaDetailPage from './pages/RcaDetailPage';
import IngestionPage from './pages/IngestionPage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  const dispatch = useAppDispatch();
  const status = useAppSelector((s) => s.auth.status);
  const handleLogout = useLogout();

  // On boot (and whenever the session cache refreshes) rehydrate auth state.
  const { data: session, isSuccess, isError } = useGetSessionQuery();
  useEffect(() => {
    if (isSuccess && session?.authenticated && session.user) {
      dispatch(setAuthenticated(session.user));
    } else if (isError || (isSuccess && !session?.authenticated)) {
      dispatch(setAnonymous());
    }
  }, [isSuccess, isError, session, dispatch]);

  const authed = status === 'authenticated';

  const nav: NavLinkItem[] = [
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/ingestion', label: 'Ingestion' },
    { href: '/anomalies', label: 'Anomalies' },
    { href: '/rca', label: 'RCA' },
    { href: '/logout', label: 'Logout', logout: true, onClick: handleLogout },
  ];

  return (
    <AppShell brand="Analytics Platform" nav={nav} showNav={authed}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="/anomalies"
          element={
            <RequireAuth>
              <AnomaliesPage />
            </RequireAuth>
          }
        />
        <Route
          path="/anomalies/:id"
          element={
            <RequireAuth>
              <AnomalyDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/rca"
          element={
            <RequireAuth>
              <RcaPage />
            </RequireAuth>
          }
        />
        <Route
          path="/rca/:id"
          element={
            <RequireAuth>
              <RcaDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/ingestion"
          element={
            <RequireAuth>
              <IngestionPage />
            </RequireAuth>
          }
        />
        <Route path="/" element={<Navigate to={authed ? '/dashboard' : '/login'} replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  );
}
