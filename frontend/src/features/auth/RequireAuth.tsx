import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAppSelector } from '../../store/hooks';

export interface RequireAuthProps {
  children: ReactNode;
}

// Gate for authed routes. status === 'unknown' -> boot spinner; 'anonymous' ->
// redirect to /login preserving the requested path; 'authenticated' -> render.
export function RequireAuth({ children }: RequireAuthProps) {
  const status = useAppSelector((s) => s.auth.status);
  const location = useLocation();

  if (status === 'unknown') {
    return <div className="arc-spinner">Loading…</div>;
  }
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}
