# Verification — React 18 SPA (ARC stand-in), SLICE-1 STEP 2

Build against the already-shipped `/api` REST endpoints. All work in the worktree
`.worktrees/react-spa/frontend/`. This step is frontend-only; no Python touched.

## Environment
- Node v24.22.0 / npm v11.19.1 (win32-arm64).
- `NODE_OPTIONS=--use-system-ca` set for every npm/npx/vite command (corporate TLS proxy).
- PowerShell 5.x; commands chained with `;`.

## What was run and the results

### 1. `npm install`
`$env:NODE_OPTIONS="--use-system-ca"; npm install`
- Result: SUCCESS. 208 packages added, 209 audited in ~20s. No mid-stream proxy breakage (no retry needed).
- Notes: npm reported 9 audit vulnerabilities (transitive, dev toolchain) and an esbuild
  `install-scripts` advisory. `npx vite --version` -> `vite/6.0.7 win32-arm64` confirms the esbuild
  binary resolved and the toolchain runs. Not blocking.

### 2. Typecheck — `npx tsc --noEmit` (primary gate, strict)
- Result: SUCCESS, 0 errors.
- One fix during setup: removed the `tsconfig.node.json` project reference (TS6310: a referenced
  project may not disable emit). `vite.config.ts` is type-checked by Vite's own pipeline; the app
  `tsconfig.json` (strict, `noUnusedLocals`/`noUnusedParameters`) covers `src`.

### 3. Unit tests — `npx vitest run`
- Result: SUCCESS. 1 file, 10 tests passed (~1.5s).
- Coverage: the load-bearing ARC DOM contracts — `TextField` emits `<input name="username">`;
  `Button type="submit"` emits `<button type="submit">`; `DataTable` emits semantic `<tbody><tr>`
  rows + an empty-state row carrying its testid; `DetailPanel` emits `.detail-label`/`.detail-value`
  with exact label text; `Badge` applies the kind-value class; `KpiCard` forwards the kpi testids;
  `EmptyState` renders `.empty-state`; `NavBar` renders logout as `<a href="/logout">`.
- Only warnings: React Router v6 future-flag notices (benign).

### 4. Production build — `npm run build` (`tsc --noEmit && vite build`) (required gate)
- Result: SUCCESS. 81 modules transformed, built in ~1.3s.
- Output written to `frontend/dist/`:
  - `dist/index.html` (0.41 kB)
  - `dist/assets/index-BeWeXrix.css` (6.31 kB)
  - `dist/assets/index-T09DOezB.js` (431.00 kB, gzip 144.88 kB)
- `cytoscape`/`react-cytoscapejs` are installed but tree-shaken out of the bundle this step: the
  RCA graph is a DEFERRED placeholder (only the panel + `rca-graph-unavailable` state render, no
  real Cytoscape wiring). STEP 3 wires the real graph using those already-installed deps.

## Python-untouched confirmation
`git -C <worktree> status --short` shows only `?? .agents/` and `?? frontend/` (both untracked).
No tracked file is modified; `data_source.py`, `app.py`, and `api/` are unchanged. `frontend/dist`
and `frontend/node_modules` are excluded by `frontend/.gitignore` and do not appear in status.

## DOM-shape / testid contracts (confirmed by inspection; full Playwright BDD NOT run this step)
- Login: native `<input name="username">` / `<input name="password">`; submit is
  `<button type="submit">` inside the `login-form`; successful login `navigate('/dashboard')`.
- Logout: `<a href="/logout">` in the navbar whose `onClick` prevents default, fires
  `POST /api/logout`, clears auth, and client-redirects to `/login` (not a `<button>`).
- `DataTable`: semantic `<table><thead><tr><th>…</thead><tbody><tr>…</tbody></table>`; anomaly/rca
  rows carry `data-id="<id>"`; row View links are real `<a href="/anomalies/:id">` /
  `<a href="/rca/:id">` (React Router `<Link>`).
- URL query-param contract (design §7 Option A, REQUIRED): severity filter pushes
  `/anomalies?severity=`, status filter pushes `/rca?status=`, a successful RCA status update pushes
  `/rca/:id?success=1` and renders `success-message`; filters hydrate from the query string on load.
- `src/testids.ts` reproduces the design §7 testid list character-for-character.

## Design-doc conflicts flagged
None. All fixed decisions and DOM contracts in the instruction match design sections 3/4/6/7.
The design doc is explicit that `login_page.py`'s `error-message` selector is stale (it matches
`login-error`/`.error-message`/`.alert-danger`); per the design §7 testid list the SPA renders
`data-testid="error-message"` as specified — this is a pre-existing bdd-framework mismatch, not a
conflict introduced here, and the bdd-framework is out of scope for this step.
