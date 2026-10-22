# Implementation Plan — WebSocket live-push channel (DEFERRED [LATER] slice)

Design authority: `c:\Users\acoak\.kiro\projects\aws-lab\.agents\designs\ui-react-migration-design.md`
§3 ("Live-mode refresh — polling now, WebSocket seam later") and §9 step 5 ([LATER]). The design is
authoritative; where this plan and the design conflict, the design wins. This slice implements the
**[LATER]** WebSocket phase that §9 explicitly deferred, following the seam §3 designed-for.

## Path correction (FLAG — read before starting)

The step prompt gives frontend/backend paths with an extra `mock-app` segment
(`...\ws-livepush\mock-app\frontend\` and `...\ws-livepush\mock-app\`). That is wrong for this
worktree. Verified by listing the tree: the worktree root **is** the mock-app directory. Actual
locations (use these absolute paths throughout):

- Backend (Flask): `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\` — contains
  `app.py`, `run.py`, `requirements.txt`, `data_source.py`, `api\__init__.py`, `tests\`.
- Frontend (React SPA): `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\frontend\`
  — contains `vite.config.ts`, `package.json`, `src\`.

## Seam-name correction (FLAG)

The step prompt and design call the seam `useLivePolling`. In the code the seam is the function
`useLivePolling` exported from the file `frontend\src\features\live\useLiveQuery.ts` (the earlier
greps for `useLivePolling` returned nothing only because they searched the wrong, extra-`mock-app`
path). It returns `{ pollingInterval, mode }` and is consumed by `DashboardPage.tsx` (dashboard +
charts queries), `AnomaliesPage.tsx`, `RcaPage.tsx`, and `IngestionPage.tsx`. This file is the
single swap point — no page/component changes.

## No conflicts with the design

The design's §3 seam intent is honoured exactly: WS replaces `<meta refresh>`/polling, `useLivePolling`
is the single swap point, a connected socket dispatches `api.util.invalidateTags([...])` into the RTK
Query cache (Redux is the push sink), and polling remains the fallback when the socket is down. The
only deviations from the step prompt are the two path/name corrections above; neither conflicts with
the design.

## Decisions baked in (grounded in the code read)

- **WS library: `flask-sock` (pinned `==0.7.0`).** Confirmed on PyPI as the latest release; its only
  transitive deps are `simple-websocket` → `wsproto`, all pure-Python (no native build, ARM64-safe).
  It is explicitly compatible with the Flask dev server used by `run.py`. `flask-socketio`/eventlet/
  gevent are NOT used (no blocker found). Content was rephrased for compliance with licensing
  restrictions. Sources: [flask-sock PyPI](https://pypi.org/project/flask-sock/),
  [flask-sock CHANGES](https://github.com/miguelgrinberg/flask-sock/blob/main/CHANGES.md),
  [wsproto docs](http://python-hyper.org/projects/wsproto/en/0.13.0/index.html).
- **Demo/simulated push FIRST.** The `/ws` endpoint emits SIMULATED events on a 3–5s timer in demo
  mode. No LocalStack/Postgres/Gremlin source is wired — that is the documented LATER follow-on.
- **Auth reuses the Flask session cookie.** `/api/*` uses `@login_required` which checks
  `session['user']` (read in `app.py`). The WS upgrade carries the same session cookie, so the WS
  handler validates `session.get('user')` and rejects unauthenticated upgrades, consistent with the
  API. flask-sock handlers run inside the Flask request/app context, so `flask.session` is available.
- **Route placement.** `/ws` is a specific rule; Flask matches it ahead of the `<path:path>` SPA
  catch-all in `app.py`. It does not touch `/api/*`, `/__reset`, `/static`, or `/login`. The
  catch-all already `abort(404)`s on `api/...`; `/ws` needs no change there because specific rules win.
- **Dev proxy.** Add a `ws: true` proxy entry for `/ws` in `frontend\vite.config.ts` so the browser
  sees a single origin in dev (mirrors the existing `/api` proxy and the single-origin design).
- **Swap logic at the seam.** `useLivePolling` opens the socket (via a small client module) only when
  `mode === 'live'` is not required — the socket is attempted whenever a live/demo session exists, but
  **demo semantics are preserved**: if the socket is DOWN, `pollingInterval` falls back to the existing
  mode-derived value (live → `refresh_seconds*1000`, demo → 0). If the socket is UP, `pollingInterval`
  is 0 (socket drives freshness) and received events dispatch `invalidateTags`. This keeps today's
  demo(no-poll)/live(poll) behaviour as the exact fallback and makes the socket an additive overlay.

## Envelope shape (backend emits, frontend consumes)

```json
{ "type": "anomaly" | "rca" | "ingestion", "event": "created" | "updated", "id": 1 }
```

`id` is optional/minimal and advisory only — the frontend keys off `type` to decide which tags to
invalidate (it does not need a full payload; invalidateTags triggers a refetch). Keep fields coherent
with existing demo shapes; do not invent fields the SPA can't handle.

## Event type → RTK Query tags map (design §3 cache-tag reasoning)

| `type`      | tags to invalidate                      |
|-------------|-----------------------------------------|
| `anomaly`   | `['Anomalies', 'Charts', 'Dashboard']`  |
| `rca`       | `['RcaList']`                           |
| `ingestion` | `['Ingestion']`                         |

These mirror the existing `acknowledgeAnomaly` invalidation set (Anomalies+Charts+Dashboard) and the
`RcaList`/`Ingestion` providesTags in `frontend\src\api\apiSlice.ts`. `invalidateTags` is the safe
default; `upsertQueryData` is not used (events carry no full payload).

---

## Steps

- [ ] 1. Pin `flask-sock==0.7.0` in requirements and install it into the active env.
      Add the line (with a short comment that it is pure-Python: simple-websocket → wsproto, ARM64-safe,
      no native build) after the `flask-cors` line.
      Files: `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\requirements.txt`
      Verify (PowerShell, proxy works for pip): from the worktree root run
      `pip install -r requirements.txt` then
      `python -c "import flask_sock, simple_websocket, wsproto; print(flask_sock.__name__)"` — prints
      `flask_sock` with no import error. Confirm nothing native was pulled:
      `pip show flask-sock simple-websocket wsproto` lists all three and no psycopg2/pyarrow appears in
      `pip freeze`.

- [ ] 2. Add the `/ws` WebSocket endpoint with the simulated emitter in a new module, wired into `app.py`.
      Create `ws.py` exposing `init_websocket(app, login_required)` that constructs `Sock(app)` and
      registers `@sock.route('/ws')`. In the handler: reject the upgrade if `flask.session.get('user')`
      is falsy (close immediately / return) so it matches the `@login_required` gate on `/api/*`. On an
      authenticated connection in DEMO mode (`os.environ.get('LAB_DATA_SOURCE','demo') != 'live'`), loop
      sending the JSON envelope every 3–5s, cycling `type` through `anomaly`/`rca`/`ingestion` with
      `event:"updated"` and a plausible demo `id`; stop cleanly when the client disconnects
      (`simple_websocket.ConnectionClosed`). In LIVE mode, accept the connection and no-op (emit nothing)
      — documented as the real-lab follow-on; must not require the lab to be running. Do NOT modify
      `data_source.py`. In `app.py`, call `init_websocket(app, login_required)` AFTER the blueprint is
      registered and BEFORE/independent of the catch-all (placement does not matter for matching since
      `/ws` is a specific rule, but register it alongside the blueprint for clarity). Add a module-level
      comment that `/ws` must not shadow `/api/*`, `/__reset`, `/static`, or the SPA catch-all.
      Files: new `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\ws.py`;
      edit `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\app.py`
      Verify: `python -c "from app import app; print([str(r) for r in app.url_map.iter_rules() if '/ws' in str(r)])"`
      from the worktree root prints a rule for `/ws`; the existing `pytest tests\test_api_endpoints.py`
      still passes (no route regression). Full smoke in step 6.

- [ ] 3. Add backend unit tests for the WS endpoint (auth gate + demo emit + live no-op).
      Use flask-sock's test support: `Sock` lets you connect with the Flask `test_client`'s WebSocket
      test harness, or assert the auth rejection by connecting without `session['user']`. Match the
      existing pytest style in `tests\test_api_endpoints.py` (autouse demo-reset fixture, authenticated
      vs `anon_client`). Cover: (a) unauthenticated upgrade is rejected/closed; (b) authenticated demo
      connection receives at least one well-formed envelope within a short bounded wait, with
      `type ∈ {anomaly,rca,ingestion}` and `event ∈ {created,updated}`; (c) in live mode
      (`monkeypatch.setenv('LAB_DATA_SOURCE','live')`) the connection opens and emits nothing within the
      same bounded wait. Keep the timer short or injectable so the test is fast and deterministic
      (e.g. read the interval from an env/arg the test can shrink).
      Files: new `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\tests\test_ws.py`
      Verify: from the worktree root `python -m pytest tests\test_ws.py -q` — all new tests pass.

- [ ] 4. Add the frontend socket client module plus the pure event→tags mapping function, with unit tests.
      Create `frontend\src\features\live\liveSocket.ts` exporting: (a) a pure
      `tagsForEvent(type: string): TagDescription[]` implementing the map above (anomaly→
      Anomalies+Charts+Dashboard, rca→RcaList, ingestion→Ingestion; unknown type → `[]`); (b) a
      `LiveSocket` class / `createLiveSocket(dispatch)` that opens `new WebSocket` to a `/ws` URL derived
      from `window.location` (ws/wss scheme, same origin so the Vite proxy applies in dev), parses each
      message, and on a valid envelope dispatches `api.util.invalidateTags(tagsForEvent(type))`; with
      reconnect/backoff (capped exponential, e.g. 1s→max ~15s) and `onopen`/`onclose` callbacks so the
      seam can track connected-state. Keep it TS-strict (no `any`; type the envelope). Add unit tests in
      the existing vitest style (see `src\features\auth\__tests__\authErrorMiddleware.test.ts`) covering
      `tagsForEvent` for each type + unknown, and that a received message dispatches `invalidateTags` with
      the mapped tags (mock `WebSocket` / spy on a mock dispatch — jsdom has no real WebSocket, so provide
      a minimal stub like the `react-cytoscapejs` mock pattern in `graph\__tests__\RcaGraph.test.tsx`).
      Files: new `frontend\src\features\live\liveSocket.ts`;
      new `frontend\src\features\live\__tests__\liveSocket.test.ts`
      Verify: from `frontend\` run `$env:NODE_OPTIONS="--use-system-ca"; npx vitest run src/features/live`
      — new tests pass.

- [ ] 5. Swap the socket in behind the `useLivePolling` seam (socket-up → poll off; socket-down → fallback poll).
      Modify `useLivePolling` in `frontend\src\features\live\useLiveQuery.ts` so it additionally: creates/
      owns a `LiveSocket` (via `createLiveSocket(dispatch)` using `useAppDispatch`) inside a `useEffect`
      that opens on mount and closes on unmount; tracks a `connected` boolean in state via the socket's
      onopen/onclose. Decision logic returned to callers is unchanged in shape (`{ pollingInterval, mode }`)
      so NO page changes: when `connected` is true, return `pollingInterval = 0` (socket drives freshness);
      when false, return the existing mode-derived value (`mode==='live' && refresh_seconds>0 ?
      refresh_seconds*1000 : 0`). This preserves demo(no-poll)/live(poll) as the exact fallback and makes
      the socket additive. Keep the file TS-strict. Add a focused unit test for the decision logic as a
      small pure helper (e.g. extract `decidePollingInterval({connected, mode, refreshSeconds})` and test:
      connected→0; disconnected+live→refreshSeconds*1000; disconnected+demo→0) in the existing vitest style.
      Files: edit `frontend\src\features\live\useLiveQuery.ts`;
      new `frontend\src\features\live\__tests__\useLiveQuery.test.ts`
      Verify: from `frontend\` run `$env:NODE_OPTIONS="--use-system-ca"; npx vitest run src/features/live`
      — decision-logic tests pass; then the full suite in step 7 confirms no page regressions.

- [ ] 6. Add the `/ws` dev proxy entry to Vite.
      In `frontend\vite.config.ts`, add under `server.proxy` a `'/ws'` entry targeting
      `http://localhost:5000` (or `ws://localhost:5000`) with `ws: true` and `changeOrigin: true`,
      alongside the existing `/api` entry. This lets the single-origin `new WebSocket` URL resolve to
      Flask in dev.
      Files: edit `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\frontend\vite.config.ts`
      Verify: from `frontend\` run `$env:NODE_OPTIONS="--use-system-ca"; npx tsc --noEmit` — config and
      all TS compiles clean (the proxy change is also exercised live in the step 8 smoke).

- [ ] 7. Run the full frontend check (type-check + build + all unit tests) to confirm TS-strict and no regressions.
      No new files. This gates the whole frontend change set (seam swap must not break existing page tests).
      Files: none (verification only).
      Verify: from `frontend\` run `$env:NODE_OPTIONS="--use-system-ca"; npm run build` (which runs
      `tsc --noEmit && vite build`) then `$env:NODE_OPTIONS="--use-system-ca"; npm test` (vitest run) —
      build succeeds, all tests green including existing ARC/auth/graph/page tests.

- [ ] 8. Run the full backend test suite and a live WS smoke, then confirm port 5000 is released.
      No new files. Confirms the WS endpoint serves concurrently with HTTP on the dev server and the
      documented run invocation works. Use the reloader-OFF invocation from the constraints.
      Files: none (verification only).
      Verify (PowerShell, from the worktree root; chain with `;`):
      1. `python -m pytest tests -q` — all backend tests pass (API + new WS).
      2. Start the server in the background with the documented invocation:
         `python -c "from app import app; app.run(port=5000, debug=False, use_reloader=False)"`
         (flask-sock runs on the threaded dev server; if a single WS blocks HTTP during the smoke, pass
         `threaded=True` to `app.run(...)` and record that exact invocation here as the dev WS command).
      3. Smoke HTTP still works: `Invoke-WebRequest http://localhost:5000/api/session` returns a response
         (401 JSON when unauthenticated — acceptable, proves HTTP serves).
      4. Smoke WS: a short Python `simple-websocket` client that first POSTs `/api/login`
         (`{"username":"u","password":"p"}`) to get the session cookie, then connects to `ws://localhost:5000/ws`
         with that cookie and reads one message within ~6s; assert it parses as the envelope with a valid
         `type`. (Unauthenticated connect should be refused — optionally assert that too.)
      5. Stop the background server; then confirm the port is free:
         `Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue` returns nothing.

---

## Files touched (summary, absolute paths)

Add:
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\ws.py`
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\tests\test_ws.py`
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\frontend\src\features\live\liveSocket.ts`
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\frontend\src\features\live\__tests__\liveSocket.test.ts`
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\frontend\src\features\live\__tests__\useLiveQuery.test.ts`

Edit:
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\requirements.txt`
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\app.py`
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\frontend\src\features\live\useLiveQuery.ts`
- `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\ws-livepush\frontend\vite.config.ts`

Do NOT touch: `data_source.py` (design + scope constraint), any page/component (`src\pages\*`,
`src\components\*`), the `/api` blueprint, `/__reset`, or the SPA catch-all logic.

## Documented follow-on (LATER)

Real-lab event source: replace the demo timer in `ws.py` with a source driven by LocalStack/Postgres/
Gremlin change events in live mode. The envelope shape and the frontend seam stay identical — only the
server-side producer changes. Out of scope for this slice.

## Environment constraints (baked into the verify steps)

- Every `npm`/`npx`/`vite` command is prefixed with `$env:NODE_OPTIONS="--use-system-ca"` (corporate
  TLS proxy). `pip install` works through the proxy as-is.
- PowerShell 5.1: chain with `;` (not `&&`); no `-SkipHttpErrorCheck` on `Invoke-WebRequest`.
- Flask reloader OFF for the smoke: `app.run(port=5000, debug=False, use_reloader=False)`; add
  `threaded=True` only if a WS connection is observed to block HTTP, and record that exact invocation.
- Confirm port 5000 free before (verified free at plan time) and after the smoke.
- Pure-Python only: flask-sock → simple-websocket → wsproto. Do NOT reintroduce psycopg2/pyarrow.
```