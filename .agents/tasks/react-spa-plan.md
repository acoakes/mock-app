# Implementation Plan — React 18 SPA (ARC stand-in), SLICE-1 STEP 2

Build a React 18 SPA (Vite + TypeScript + Redux Toolkit + RTK Query + React Router v6) with a
home-grown `@arc` stand-in component library, against the already-shipped `/api` REST endpoints,
inside the worktree `c:\Users\acoak\.kiro\projects\mock-app\.worktrees\react-spa\`. All new code
lives under `frontend/`. This is a pure frontend add — do NOT modify any Python file.

## Context grounded in the repo (read before you start)

- STEP 1 is already done and committed: `api/__init__.py` serves all 11 `/api` endpoints exactly as
  the design §2/§3/§6 specify (dashboard, anomalies, anomalies/:id, anomalies/:id/acknowledge [POST],
  charts, rca, rca/:id, rca/:id/status [POST, JSON body `{status}`], rca/:id/graph, login [POST],
  session [GET, returns `authenticated/user/mode/refresh_seconds`], logout [POST]). `app.py` registers
  the blueprint and adds `CORS(..., supports_credentials=True)` scoped to `/api/*` with origin
  `SPA_ORIGIN` (default `http://localhost:3000`). Response shapes are confirmed in the source — build
  the SPA types to match them exactly.
- The Flask app runs on `http://localhost:5000` (`run.py`, README). Auth is a session cookie; any
  non-empty username+password passes.
- DOM contracts and testids are harvested from the live Jinja templates (`templates/*.html`) and the
  BDD page objects at `c:\Users\acoak\.kiro\projects\bdd-framework\pages\*.py`. Those page objects
  are the real consumers; the SPA must satisfy their selectors (details in each item below).
- Demo data shapes (for reference while typing responses): anomaly `{id:int, description, severity
  HIGH|MEDIUM|LOW, status open|acknowledged, timestamp}`; rca `{id:int, title, status
  open|in_progress|resolved, root_cause, recommendation}`; kpi `{name, value, unit}` (exactly 5);
  charts `{by_vendor,by_severity,over_time}` each `{labels:[],values:[]}`; ingestion
  `{pm_files:[{key,vendor,size,stage,records|null}], tickets:[{ticket_id,ticket_type,vendor,window_start,summary}]}`.
- CSS tokens/colours to port come from `static/style.css`; the HIGH/MEDIUM/LOW doughnut colour map
  (`#c0392b`/`#e67e22`/`#27ae60`) and chart options come from `static/dashboard_charts.js`; the
  graph node-colour map and `breadthfirst` layout come from `static/rca_graph.js`.
- Node is v24 / npm v11 on this machine. `frontend/` does not exist yet; the worktree is clean on
  branch `feat/react-spa`.

## Design decisions I am fixing for the implementer (design doc wins where it speaks)

- Dev single origin via the Vite proxy (`server.proxy` `/api` -> `http://localhost:5000`) so the
  session cookie "just works"; `credentials:'include'` on the base query. This is the design's §6
  recommended local setup. The build itself is origin-agnostic (`VITE_API_BASE_URL ?? '/api'`).
- The RCA graph is a DEFERRED placeholder this step (design §9 step 3 is a later SLICE-1 step):
  `RcaGraph.tsx` renders only `rca-graph-panel` + `rca-graph-unavailable`. Install cytoscape deps,
  but do NOT wire real Cytoscape rendering yet. Dashboard charts ARE in scope and fully built.
- Filters and the RCA success marker are pushed to the URL via the router (design §7 Option A,
  promoted to REQUIRED), with on-load hydration from the query string.

## Conflict / risk notes (flagged per instructions)

- Login error testid mismatch (pre-existing, not ours to fix): `login_page.py::ERROR_MESSAGE` is
  `[data-testid='login-error'], .error-message, .alert-danger` — it does NOT match the design's
  `error-message` testid or the `.error` class. The design §7 testid list says render `error-message`;
  follow the design (render `data-testid="error-message"`). Do not alter the bdd-framework. The error
  path is only exercised by negative login scenarios; the load-bearing contracts (username/password
  `name=`, submit button, logout anchor, `/dashboard` redirect) are all satisfied below.
- An SPA can reach `networkidle` before RTK Query resolves. That is a bdd-framework page-object
  concern (design §7 "async waitFor tuning") and is NOT in this step's scope — do not edit
  bdd-framework here. This step's job is to reproduce the testids/routes/DOM shapes faithfully.
- `data_source` is reused as-is; do not touch it or any Python. The API is already byte-shape stable.

---

- [ ] 1. Scaffold the Vite + React 18 + TypeScript project under `frontend/`.
      Create `frontend/package.json` (name, `"type":"module"`, scripts `dev`/`build`/`preview`/`test`),
      pinning exact versions: `react@18.x`, `react-dom@18.x`, `@reduxjs/toolkit`, `react-redux`,
      `react-router-dom@6.x`, `chart.js`, `react-chartjs-2`, `cytoscape`, `react-cytoscapejs` as deps;
      `vite`, `@vitejs/plugin-react`, `typescript`, `@types/react`, `@types/react-dom`, `vitest`,
      `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` as devDeps. Create
      `frontend/index.html` (root `<div id="root">` + `<script type="module" src="/src/main.tsx">`),
      `frontend/vite.config.ts` (`base:'/'`, `plugins:[react()]`, `server.proxy` mapping `/api` ->
      `http://localhost:5000` with `changeOrigin:true`, `build.outDir:'dist'`, the `@arc` alias ->
      `src/components/arc`, and a vitest `test` config with `environment:'jsdom'` + a setup file),
      `frontend/tsconfig.json` + `frontend/tsconfig.node.json` (strict, `jsx:'react-jsx'`,
      `moduleResolution:'bundler'`, `paths` mapping `@arc/*` -> `src/components/arc/*` to match the
      Vite alias), `frontend/src/vite-env.d.ts`, `frontend/src/test/setup.ts` (imports
      `@testing-library/jest-dom`), and `frontend/.gitignore` excluding `node_modules` and `dist`.
      Files: frontend/package.json, frontend/index.html, frontend/vite.config.ts,
      frontend/tsconfig.json, frontend/tsconfig.node.json, frontend/src/vite-env.d.ts,
      frontend/src/test/setup.ts, frontend/.gitignore
      Verify: in `frontend/`, run `$env:NODE_OPTIONS="--use-system-ca"; npm install` then
      `$env:NODE_OPTIONS="--use-system-ca"; npx tsc --noEmit` — install completes and typecheck passes
      (no app code yet, so tsc should be clean). PowerShell: chain with `;`, never `&&`.

- [ ] 2. Create `src/testids.ts` reproducing the design §7 testid list EXACTLY.
      Export a single `const TESTIDS` object (or flat named consts) covering every id: login
      (`login-form`, `username-input`, `password-input`, `login-button`, `error-message`); dashboard
      (`kpi-card`, `kpi-name`, `kpi-value`, `dashboard-chart`, `date-filter-form`, `date-from`,
      `date-to`, `apply-filter`, `empty-state`); anomalies (`anomaly-table`, `anomaly-row`,
      `anomaly-severity`, `anomaly-status`, `severity-filter`, `acknowledge-button`,
      `anomaly-detail-panel`, `anomaly-description`); rca (`rca-table`, `rca-row`, `rca-status`,
      `status-filter`, `rca-detail-panel`, `root-cause-description`, `recommendation-text`,
      `status-update-select`, `save-status-button`, `success-message`, `rca-graph-panel`, `rca-graph`,
      `rca-graph-unavailable`); ingestion (`pm-file-table`, `pm-file-row`, `pm-file-stage`,
      `pm-file-empty`, `ticket-table`, `ticket-row`, `ticket-type`, `ticket-empty`,
      `ingestion-live-note`, `ingestion-demo-note`). These strings are the hard contract — match the
      template values character-for-character.
      Files: frontend/src/testids.ts
      Verify: `$env:NODE_OPTIONS="--use-system-ca"; npx tsc --noEmit` in `frontend/` passes.

- [ ] 3. Port the CSS and define the `@arc` theme stylesheet.
      Port `static/style.css` verbatim into `frontend/src/styles/arc.css` (navbar `#2c3e50`, buttons,
      `.data-table`, `.kpi-card`, `.detail-panel`, `.severity-*`, `.stage-*`, `.ticket-*`, login
      card, `.success`/`.error`/`.empty-state`, `.rca-graph`). Import it once from `src/main.tsx`.
      Keep class names identical so the ported visuals and the page objects' CSS fallbacks stay valid.
      Files: frontend/src/styles/arc.css
      Verify: deferred to item 13 (build). No standalone command.

- [ ] 4. Build the Redux store with `auth` + `ui` slices and typed hooks.
      Create `src/features/auth/authSlice.ts` (state `{user:string|null, status:'unknown'|
      'authenticated'|'anonymous'}`, reducers to set authenticated/anonymous/unknown), and
      `src/features/ui/uiSlice.ts` (state `{anomalySeverityFilter:''|'HIGH'|'MEDIUM'|'LOW',
      rcaStatusFilter:''|'open'|'in_progress'|'resolved', dateFrom:string, dateTo:string}` with
      setter reducers). Create `src/store/index.ts` (`configureStore({reducer:{auth, ui,
      [api.reducerPath]:api.reducer}, middleware: gDM => gDM().concat(api.middleware)}}`) and
      `src/store/hooks.ts` (typed `useAppDispatch`/`useAppSelector`, `RootState`/`AppDispatch` from
      the store). Item 5 creates `api`; to avoid an ordering snag, do item 5 first or stub the import.
      Files: frontend/src/features/auth/authSlice.ts, frontend/src/features/ui/uiSlice.ts,
      frontend/src/store/index.ts, frontend/src/store/hooks.ts
      Verify: `npx tsc --noEmit` in `frontend/` passes (with item 5 present).

- [ ] 5. Create the RTK Query API slice per design §3 (do this alongside/just before item 4).
      Create `src/api/apiSlice.ts` with `createApi({reducerPath:'api', baseQuery: fetchBaseQuery({
      baseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api', credentials:'include'}), tagTypes:
      ['Dashboard','Charts','Anomalies','Anomaly','RcaList','Rca','RcaGraph','Ingestion','Session']})`.
      Define TypeScript response types and every endpoint exactly: `getSession` (providesTags
      `['Session']`), `getDashboard`/`getCharts` (params `{date_from,date_to}`, tags `Dashboard`/
      `Charts`), `getAnomalies` (param `{severity}`, tag `Anomalies`), `getAnomaly(id)` (tag
      `{type:'Anomaly',id}`), `acknowledgeAnomaly(id)` mutation (POST
      `anomalies/${id}/acknowledge`, invalidates `['Anomalies',{type:'Anomaly',id},'Charts',
      'Dashboard']`), `getRcaList` (param `{status}`, tag `RcaList`), `getRca(id)` (tag
      `{type:'Rca',id}`), `getRcaGraph(id)` (tag `{type:'RcaGraph',id}`), `updateRcaStatus({id,status})`
      mutation (POST `rca/${id}/status`, body `{status}`, invalidates `['RcaList',{type:'Rca',id}]`),
      `getIngestion` (tag `Ingestion`). Export the generated hooks. The cache-tag invalidations must
      be EXACTLY as stated (acknowledge -> Anomalies+Anomaly+Charts+Dashboard; updateRcaStatus ->
      RcaList+Rca).
      Files: frontend/src/api/apiSlice.ts
      Verify: `npx tsc --noEmit` in `frontend/` passes.

- [ ] 6. Build the home-grown `@arc` stand-in component library (presentational only).
      Create under `src/components/arc/` one coherent set of presentational components (no Redux, no
      fetching, each forwards `data-testid`, `className`, `children`): `AppShell`, `NavBar`,
      `PageHeading`, `KpiCard`, `KpiGrid`, `DataTable`, `DetailPanel`, `Select`, `TextField`,
      `Button`, `DateRangeFilter`, `Banner`/`EmptyState`, `Badge`, plus an `index.ts` barrel.
      Hard DOM-shape contracts (confirmed against the templates and page objects — these are
      load-bearing, not optional):
        - `TextField` renders a NATIVE `<input name=...>` (login needs `name="username"` and
          `name="password"`; `login_page.py` binds via `input[name='username']`).
        - `Button` with `type="submit"` renders a real `<button type="submit">`.
        - `DataTable` renders a SEMANTIC `<table><thead><tr><th>…</tr></thead><tbody>…</tbody></table>`
          (page objects count `tbody tr` and subtract one header row). Props:
          `{columns, rows, rowKey, renderRow?, emptyText, testid}`; render an empty-row `<tr><td
          colspan=…>` carrying an empty-state testid when rows are empty (ingestion needs
          `pm-file-empty`/`ticket-empty`).
        - `DetailPanel` renders `.detail-row` blocks each with `.detail-label` + `.detail-value`;
          the label text must be exact (`rca_page.py` selects the Status row via
          `.detail-row:has(.detail-label:text-is('Status')) .detail-value`).
        - `Select` renders a native `<select name=...>` with `<option>`s.
        - `Badge` applies `severity-*`/`stage-*`/`ticket-*` classes by kind.
      Add a one-line TS prop-contract (exported type) per component so the real ARC can satisfy it.
      Files: frontend/src/components/arc/*.tsx, frontend/src/components/arc/index.ts
      Verify: item 7 adds unit tests; run them there. For now `npx tsc --noEmit` passes.

- [ ] 7. Add React Testing Library unit tests for the ARC primitives.
      Cover the load-bearing DOM shapes: `TextField` emits `<input name="username">`; `Button
      type="submit"` emits `<button type="submit">`; `DataTable` emits `<tbody><tr>` rows and an
      empty-state row with its testid when empty; `DetailPanel` emits `.detail-label`/`.detail-value`
      with exact label text; `Badge` applies the right class; every component forwards its
      `data-testid`.
      Files: frontend/src/components/arc/__tests__/*.test.tsx
      Verify: `$env:NODE_OPTIONS="--use-system-ca"; npx vitest run` in `frontend/` — all ARC tests pass.

- [ ] 8. Create the DEFERRED RCA graph placeholder.
      Create `src/graph/RcaGraph.tsx` that takes the graph query result and renders ONLY
      `data-testid="rca-graph-panel"` wrapping either `rca-graph` (when nodes exist) or
      `rca-graph-unavailable` (empty/loading/error). Do NOT import or wire `cytoscape`/
      `react-cytoscapejs` rendering this step (deps are installed for the later slice). Add the pure
      wire->elements adapter as a stub/typed function if helpful, but it is not invoked for rendering.
      Files: frontend/src/graph/RcaGraph.tsx
      Verify: covered by item 11/13; `npx tsc --noEmit` passes.

- [ ] 9. Build `DashboardCharts.tsx` (charts ARE in scope).
      Create `src/charts/DashboardCharts.tsx` rendering three `react-chartjs-2` charts inside a
      container with `data-testid="dashboard-chart"`: a `Bar` for `by_vendor` (canvas id
      `chart-by-vendor`), a `Doughnut` for `by_severity` (canvas id `chart-by-severity`) using the
      fixed colour map `{HIGH:'#c0392b', MEDIUM:'#e67e22', LOW:'#27ae60'}` with the PALETTE fallback
      from `dashboard_charts.js`, and a `Line` for `over_time` (canvas id `chart-over-time`). Port
      chart options verbatim (legend display/position, `beginAtZero`, `ticks.precision:0`, line
      `borderColor '#2563eb'`, fill `rgba(37,99,235,0.15)`, `tension:0.25`). Register the needed
      chart.js components. Fail safe: render the container with empty canvases while loading/on error
      (never crash) so the `[data-testid='dashboard-chart'], canvas` selector still matches.
      Files: frontend/src/charts/DashboardCharts.tsx
      Verify: covered by item 13 build; optional a focused render test under
      `frontend/src/charts/__tests__/`.

- [ ] 10. Implement the auth flow, app shell, and router.
      Create `src/features/auth/RequireAuth.tsx` (reads `auth.status`: `unknown` -> spinner,
      `anonymous` -> `<Navigate to="/login">` preserving the requested path, `authenticated` ->
      children). Create `src/App.tsx`: on mount dispatch `getSession` (200 -> authenticated, 401 ->
      anonymous); render `AppShell`/`NavBar` (brand "Analytics Platform"; links to `/dashboard`,
      `/ingestion`, `/anomalies`, `/rca`, and the logout control) only when authenticated; define
      React Router v6 routes `/login`, `/dashboard`, `/anomalies`, `/anomalies/:id`, `/rca`,
      `/rca/:id`, `/ingestion`, `/` (redirect to `/dashboard` if authed else `/login`), `*`
      (NotFoundPage), with the authed routes wrapped by `RequireAuth`. Create `src/main.tsx`
      (`createRoot`, `<Provider store>`, `<BrowserRouter>`, import `styles/arc.css`).
      CRITICAL logout contract: the logout control is an `<a href="/logout">` whose `onClick` calls
      `e.preventDefault()`, fires `POST /api/logout` (via the api slice/thunk), clears `auth`, and
      client-redirects to `/login` (so `a[href*='logout']` matches and `is_logged_in()` sees a
      visible anchor).
      Files: frontend/src/App.tsx, frontend/src/main.tsx, frontend/src/features/auth/RequireAuth.tsx
      Verify: covered by item 13 build; `npx tsc --noEmit` passes.

- [ ] 11. Implement all pages/routes (one item — same compose-ARC-primitives pattern across pages).
      Create under `src/pages/`:
        - `LoginPage.tsx`: ARC `TextField`×2 inside a `data-testid="login-form"` `<form>` with native
          `name="username"`/`name="password"` inputs and a `<button type="submit"
          data-testid="login-button">`; submit calls `POST /api/login`, on success refetch
          `getSession` and `navigate` to a URL CONTAINING `/dashboard` (hard requirement —
          `login_page.py::login()` waits for `**/dashboard**`), on failure render
          `data-testid="error-message"`.
        - `DashboardPage.tsx`: `KpiGrid`/`KpiCard` (each `kpi-card` with `kpi-name`+`kpi-value`;
          exactly 5), `DashboardCharts`, and a `date-filter-form` (`date-from`, `date-to`,
          `apply-filter`) driven by `useGetDashboardQuery`/`useGetChartsQuery({date_from,date_to})`
          from the `ui` slice; render `empty-state` when the dashboard reports empty. Apply reads/
          writes the date range through the `ui` slice.
        - `AnomaliesPage.tsx`: `severity-filter` `<select>` + `DataTable` (`anomaly-table`) of
          `anomaly-row` rows. Each row carries `data-id="<id>"`, a View link as a real
          `<a href="/anomalies/:id">` (React Router `<Link>`), cells `anomaly-severity`/
          `anomaly-status`, and an `acknowledge-button` that calls `useAcknowledgeAnomalyMutation`
          and STAYS on `/anomalies` (cache invalidation refreshes the row — matches
          `acknowledge_first_anomaly` waiting on `**/anomalies**`).
        - `AnomalyDetailPage.tsx`: `DetailPanel` (`anomaly-detail-panel`, `anomaly-description`) +
          acknowledge button via `useGetAnomalyQuery(id)`; render a not-found state on 404.
        - `RcaPage.tsx`: `status-filter` + `DataTable` (`rca-table`) of `rca-row` rows with
          `rca-status` and a View link as real `<a href="/rca/:id">`.
        - `RcaDetailPage.tsx`: `DetailPanel` (`rca-detail-panel`, `root-cause-description`,
          `recommendation-text`, and a Status detail-row whose label is exactly "Status") + a status
          `<form>` (`status-update-select`, `save-status-button`) calling `useUpdateRcaStatusMutation`;
          on success navigate to `/rca/:id?success=1` and render `success-message` (hard requirement —
          `update_status` waits for `**success=1**`). Render `RcaGraph` panel (placeholder from item 8)
          via `useGetRcaGraphQuery(id)`.
        - `IngestionPage.tsx`: two `DataTable`s — `pm-file-table` (`pm-file-row`, `pm-file-stage`,
          empty row `pm-file-empty`) and `ticket-table` (`ticket-row`, `ticket-type`, empty row
          `ticket-empty`) — plus `ingestion-live-note`/`ingestion-demo-note` chosen by session `mode`,
          via `useGetIngestionQuery`.
        - `NotFoundPage.tsx`: simple not-found view.
      Files: frontend/src/pages/LoginPage.tsx, DashboardPage.tsx, AnomaliesPage.tsx,
      AnomalyDetailPage.tsx, RcaPage.tsx, RcaDetailPage.tsx, IngestionPage.tsx, NotFoundPage.tsx
      Verify: `npx tsc --noEmit` passes; covered by the build in item 13.

- [ ] 12. Wire the URL query-param contract (filters + success marker) with on-load hydration.
      In `AnomaliesPage` and `RcaPage`, applying the filter must call `navigate` to push
      `/anomalies?severity=<value>` and `/rca?status=<value>` (so `filter_by_severity`/
      `filter_by_status` match `**/anomalies?*` / `**/rca?*`); the `ui` slice stays the source of
      truth but is kept in sync with the query string. On load, hydrate the `ui` filter FROM the
      query string (`useSearchParams`) so deep links and the post-navigation render agree. In
      `RcaDetailPage`, a successful status update navigates to a URL containing `success=1`; the page
      renders `success-message` whenever `success=1` is present (it may strip the param afterward
      without breaking the `**success=1**` glob).
      Files: frontend/src/pages/AnomaliesPage.tsx, frontend/src/pages/RcaPage.tsx,
      frontend/src/pages/RcaDetailPage.tsx (refine the pages from item 11)
      Verify: `npx tsc --noEmit` passes; full build in item 13.

- [ ] 13. Verification gate: typecheck, unit tests, and the production build.
      Run the full gate in `frontend/` in order, each with `NODE_OPTIONS=--use-system-ca`, chaining
      with `;` (PowerShell): `npm install` (if not already), then `npx tsc --noEmit`, then
      `npx vitest run`, then `npm run build`. Fix any errors surfaced here before finishing.
      Confirm `frontend/dist/` is produced with `index.html` + hashed `assets/`.
      Files: none (verification only)
      Verify: `$env:NODE_OPTIONS="--use-system-ca"; npm run build` exits 0 and writes `frontend/dist/`;
      `npx vitest run` is green; `npx tsc --noEmit` is clean.

- [ ] 14. Commit the frontend on the branch (never push).
      Stage ONLY the frontend additions by explicit path — `git add frontend .agents/tasks/react-spa-plan.md`
      (NEVER `git add -A`/`git add .`, which could sweep in build or stray artifacts). Confirm
      `frontend/node_modules` and `frontend/dist` are excluded by `frontend/.gitignore` and NOT
      staged. Commit with a Conventional-Commits message, e.g.
      `feat(spa): React 18 SPA (ARC stand-in) against /api — slice 1 step 2`. Do NOT push.
      Files: none (git only)
      Verify: `git -C <worktree> status --short` shows a clean tree after commit and
      `git show --stat HEAD` lists only `frontend/**` (plus the plan file) — no `node_modules`/`dist`
      entries, no Python files changed.

## Ordering notes

- Items 4 and 5 are mutually referential (the store imports the api reducer/middleware; pages import
  both). Create item 5 (`apiSlice.ts`) first or in the same change as item 4 so `npx tsc --noEmit`
  has both halves. Everything after item 5 depends on the store + api being present.
- Items 6-7 (ARC + its tests) gate items 9-12 (charts and pages consume ARC primitives).
- Item 8 (graph placeholder) must exist before item 11's `RcaDetailPage` imports it.
- Item 13 is the single real correctness gate (`npm run build` + `vitest`); treat a red build as a
  stop-and-fix, not a warning.
