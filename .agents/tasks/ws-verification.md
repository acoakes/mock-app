# Verification — WebSocket live-push channel (demo emitter) behind the useLivePolling seam

Branch: `feat/ws-livepush` (worktree `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush`).
First iteration (no `ws-review.json` present at start). All commands below were actually run; results
are recorded verbatim so the reviewer does not need to re-run them.

## FLAG — path/name corrections (from the plan, confirmed)

- The step prompt's paths carry an extra `mock-app` segment
  (`...\ws-livepush\mock-app\frontend\`). That directory does NOT exist in this worktree. The worktree
  root **is** the mock-app dir. Verified: `Test-Path ...\ws-livepush\mock-app` → `False`; the root
  contains `app.py`, `run.py`, `requirements.txt`, `frontend\`, `tests\`.
  - Backend: `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\`
  - Frontend: `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\frontend\`
- The seam is the function `useLivePolling` exported from
  `frontend\src\features\live\useLiveQuery.ts` (consumed by Dashboard/Anomalies/Rca/Ingestion pages).
- No conflict with the design doc (§3 / §9 step 5): WS replaces polling, `useLivePolling` is the single
  swap point, a connected socket dispatches `api.util.invalidateTags([...])` into the RTK Query cache
  (Redux is the push sink), polling is the fallback. Implemented exactly as designed-for.

## Library choice (pure-Python, ARM64-safe)

`flask-sock==0.7.0`, pinned in `requirements.txt`. Transitive deps are all pure-Python wheels
(`py3-none-any`): `simple-websocket==1.1.0` → `wsproto==1.3.2` → `h11==0.16.0`. No native build; no
eventlet/gevent; no flask-socketio. No psycopg2/pyarrow pulled.

```
Installing collected packages: h11, wsproto, simple-websocket, flask-sock
Successfully installed flask-sock-0.7.0 h11-0.16.0 simple-websocket-1.1.0 wsproto-1.3.2
```

Native-dep check (`pip freeze | Select-String "psycopg2|pyarrow"`): **no matches**.

## Backend

Commands run from the worktree root (Python 3.12.10, arm64):

- `python -c "import flask_sock, simple_websocket, wsproto; print(...)"` → `import ok: flask_sock`
- `python -c "import app"` → `app import ok` (clean)
- `python -c "from app import app; print([... '/ws' ...])"` → `ws rules: ['/ws']`
- `python -m pytest tests\test_ws.py -q` → **7 passed in 3.33s**
- `python -m pytest tests -q` (full backend suite) → **55 passed in 3.44s** (no regression)

New backend tests (`tests\test_ws.py`), using a real threaded werkzeug server + a `simple-websocket`
client (flask-sock needs a real socket upgrade, so the Flask `test_client` cannot drive WS):

- `/ws` route is registered and marked `websocket=True`.
- `WS_SIM_INTERVAL` env override + fallback; `LAB_DATA_SOURCE` → live-mode detection; every simulated
  envelope is well-formed (`type ∈ {anomaly,rca,ingestion}`, `event ∈ {created,updated}`).
- **Auth gate:** an unauthenticated upgrade is closed with no event delivered.
- **Demo emit:** an authenticated demo socket pushes a well-formed envelope within the bounded wait.
- **Live no-op:** in `LAB_DATA_SOURCE=live` an authenticated socket connects but emits nothing.

## Frontend

Commands run from `frontend\` with `$env:NODE_OPTIONS="--use-system-ca"` set first:

- `npm install` → completed (esbuild native binary resolved; build below succeeds).
- `npx tsc --noEmit` (TS strict) → clean, `EXIT=0`.
- `npx vitest run` → **7 files, 42 tests passed** (includes the 15 new tests below). The stderr lines
  are pre-existing React Router v7 future-flag warnings, not failures.
- `npm run build` (`tsc --noEmit && vite build`) → **built in 2.01s**, `EXIT=0`. Emits
  `dist/index.html`, `dist/assets/index-*.css`, `dist/assets/index-*.js`. (Chunk-size >500 kB is a
  pre-existing warning, not an error.)

New frontend tests:

- `src\features\live\__tests__\liveSocket.test.ts` (10 tests): `tagsForEvent` for each type + unknown
  (anomaly→Anomalies+Charts+Dashboard, rca→RcaList, ingestion→Ingestion, unknown→[]); `liveSocketUrl`
  ws/wss scheme; a received message dispatches `api.util.invalidateTags(mappedTags)` via a stubbed
  WebSocket (jsdom has no real WebSocket, so an injectable `socketFactory` stub is used, mirroring the
  react-cytoscapejs stub pattern); malformed / typeless messages are ignored; onOpen/onClose fire.
- `src\features\live\__tests__\useLiveQuery.test.ts` (5 tests): the pure `decidePollingInterval`
  decision — connected→0 (socket drives freshness); disconnected+live→`refreshSeconds*1000` (fallback
  poll); disconnected+demo→0; live+refresh=0→0; unknown mode→0.

## LIVE BROWSER SMOKE (the whole point of WS) — PASS

Setup: built SPA served by Flask (single origin), demo mode, reloader OFF, threaded ON, short push
cadence. Exact background server invocation:

```
$env:FLASK_SECRET_KEY="smoke-secret"; $env:WS_SIM_INTERVAL="2"; $env:LAB_DATA_SOURCE="demo";
python -c "from app import app; app.run(port=5000, debug=False, use_reloader=False, threaded=True)"
```

HTTP still serves while WS runs: `GET /api/session` → 401 (unauth JSON, proves HTTP+API);
`GET /` → 200, 420-byte SPA shell. (`threaded=True` is the recorded dev WS invocation so a blocking WS
loop does not starve HTTP; flask-sock runs on the werkzeug dev server this way.)

A headless Chromium (Playwright 1.63.0) logged in through the SPA, landed on `/dashboard`, then — AFTER
the initial data load was allowed to settle and the request log was cleared to a baseline (so nothing
counted could be the first page load, and demo mode means `pollingInterval === 0`, so no poll timer can
fire) — observed socket frames and a socket-driven refetch. Captured evidence lines:

```
EVIDENCE socket_opened url=ws://localhost:5000/ws
EVIDENCE dashboard_rendered kpi-card visible
EVIDENCE socket_frame_received payload={"type": "anomaly", "event": "updated", "id": 1}
EVIDENCE api_gets_after_baseline=2
EVIDENCE total_ws_frames=4
EVIDENCE refetch_after_push url=http://localhost:5000/api/charts?date_from=&date_to=
SMOKE_RESULT PASS
```

Interpretation: the `/ws` socket opened and received pushed envelopes; after the baseline (initial load
settled, polling off in demo mode) a `/api/charts` GET fired — the refetch driven by
`invalidateTags(['Anomalies','Charts','Dashboard'])` from the pushed `anomaly` event. This is the
pushed-update path firing end-to-end, not a timer poll.

The smoke was driven by a throwaway Playwright harness (`.agents/tasks/ws_smoke.py`), deleted after the
run per the temp-file cleanup guideline; the exact setup, selectors (`username-input`, `password-input`,
`login-button`, `kpi-card`), and evidence are recorded above so the result is reproducible without it.

Teardown: server stopped; `Get-NetTCPConnection -LocalPort 5000` → **PORT 5000 FREE**.

## Polling fallback still works

Preserved and unit-tested: when the socket is down (`connected=false`), `decidePollingInterval` returns
the original mode-derived interval — live → `refreshSeconds*1000`, demo → 0. The socket is purely
additive overlay on top of the existing demo(no-poll)/live(poll) behaviour; pages/components are
unchanged (callers still read `{ pollingInterval, mode }`).

## Documented follow-on (LATER, out of scope for this slice)

Real-lab event source: replace the demo timer in `ws.py` with a producer driven by
LocalStack/Postgres/Gremlin change events in live mode. The envelope shape and the frontend seam stay
identical — only the server-side producer changes. In live mode today the `/ws` endpoint connects and
emits nothing (does not require the lab to be running).

## Files changed

Add:
- `ws.py` — `/ws` endpoint + simulated demo emitter + live no-op.
- `tests\test_ws.py` — backend WS tests (auth gate / demo emit / live no-op + helpers).
- `frontend\src\features\live\liveSocket.ts` — socket client + pure `tagsForEvent` + reconnect/backoff.
- `frontend\src\features\live\__tests__\liveSocket.test.ts`
- `frontend\src\features\live\__tests__\useLiveQuery.test.ts`

Edit:
- `requirements.txt` — pin `flask-sock==0.7.0` (pure-Python note).
- `app.py` — `init_websocket(app, login_required)` after the blueprint; route-hygiene comment.
- `frontend\src\features\live\useLiveQuery.ts` — own a `LiveSocket`, track connected-state, swap
  polling via the pure `decidePollingInterval`.
- `frontend\vite.config.ts` — `/ws` dev proxy entry with `ws: true`.

Not touched: `data_source.py`, any page/component, the `/api` blueprint, `/__reset`, the SPA catch-all.
