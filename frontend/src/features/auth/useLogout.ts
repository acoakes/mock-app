import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLogoutMutation } from '../../api/apiSlice';
import { useAppDispatch } from '../../store/hooks';
import { setAnonymous } from './authSlice';

// The logout control is a native <a href="/logout"> (so a[href*='logout']
// matches). This hook returns the onClick that prevents default, fires
// POST /api/logout, clears auth, and client-redirects to /login.
export function useLogout() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [logout] = useLogoutMutation();

  return useCallback(
    async (e: React.MouseEvent<HTMLAnchorElement>) => {
      e.preventDefault();
      try {
        await logout().unwrap();
      } catch {
        // best-effort: clear client state even if the request fails
      }
      dispatch(setAnonymous());
      navigate('/login');
    },
    [logout, dispatch, navigate],
  );
}
