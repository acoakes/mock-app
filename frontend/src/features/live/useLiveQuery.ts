import { useGetSessionQuery } from '../../api/apiSlice';

// Live-mode refresh seam (design §3). Today this sets an RTK Query
// `pollingInterval` from the session mode/refresh_seconds (live -> poll,
// demo -> 0 = no polling, matching the server's no-<meta refresh> demo
// behaviour). This is the SINGLE place that knows "where freshness comes from":
// when the WebSocket channel lands (Phase 5) this wrapper swaps polling for a
// socket subscription + `api.util.invalidateTags`, and no component changes.
//
// Usage:
//   const { pollingInterval } = useLivePolling();
//   const result = useGetDashboardQuery(args, { pollingInterval });
export function useLivePolling(): { pollingInterval: number; mode: 'live' | 'demo' | undefined } {
  const { data } = useGetSessionQuery();
  const mode = data?.mode;
  const refreshSeconds = data?.refresh_seconds ?? 0;
  const pollingInterval = mode === 'live' && refreshSeconds > 0 ? refreshSeconds * 1000 : 0;
  return { pollingInterval, mode };
}
