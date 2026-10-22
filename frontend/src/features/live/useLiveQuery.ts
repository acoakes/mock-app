import { useEffect, useState } from 'react';
import { useGetSessionQuery } from '../../api/apiSlice';
import { useAppDispatch } from '../../store/hooks';
import { createLiveSocket } from './liveSocket';

// Live-mode refresh seam (design §3). This is the SINGLE place that knows
// "where freshness comes from". Two sources, one swap point:
//
//  - WebSocket (Phase 5, this slice): when the socket is connected it drives
//    freshness by dispatching `api.util.invalidateTags` on each pushed event
//    (see liveSocket.ts), so polling is turned OFF (pollingInterval = 0).
//  - Polling (fallback): when the socket is down/unavailable, fall back to the
//    original behaviour — live mode polls every `refresh_seconds`, demo mode
//    does not poll (matching the server's no-<meta refresh> demo behaviour).
//
// Components do NOT change: callers still read `{ pollingInterval, mode }`.
//
// Usage:
//   const { pollingInterval } = useLivePolling();
//   const result = useGetDashboardQuery(args, { pollingInterval });

/** Pure decision for the RTK Query `pollingInterval` (ms).
 *
 * Socket connected  -> 0 (socket drives freshness).
 * Disconnected+live -> refreshSeconds*1000 (fall back to polling).
 * Disconnected+demo -> 0 (no polling, as today).
 */
export function decidePollingInterval(args: {
  connected: boolean;
  mode: 'live' | 'demo' | undefined;
  refreshSeconds: number;
}): number {
  const { connected, mode, refreshSeconds } = args;
  if (connected) {
    return 0;
  }
  return mode === 'live' && refreshSeconds > 0 ? refreshSeconds * 1000 : 0;
}

export function useLivePolling(): { pollingInterval: number; mode: 'live' | 'demo' | undefined } {
  const { data } = useGetSessionQuery();
  const dispatch = useAppDispatch();
  const mode = data?.mode;
  const refreshSeconds = data?.refresh_seconds ?? 0;

  // Track whether the live-push socket is currently connected. When it is, the
  // socket drives freshness and polling is disabled; otherwise we fall back to
  // the mode-derived polling interval above.
  const [connected, setConnected] = useState(false);

  // Only open the socket once the user is authenticated (a mode is known); the
  // backend rejects unauthenticated upgrades anyway. Reopen if auth state flips.
  const authed = mode !== undefined;
  useEffect(() => {
    if (!authed) {
      return;
    }
    const socket = createLiveSocket(dispatch, {
      onOpen: () => setConnected(true),
      onClose: () => setConnected(false),
    });
    socket.connect();
    return () => {
      setConnected(false);
      socket.close();
    };
  }, [authed, dispatch]);

  const pollingInterval = decidePollingInterval({ connected, mode, refreshSeconds });
  return { pollingInterval, mode };
}
