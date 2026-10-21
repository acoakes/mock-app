# Mock Data Analytics Platform

A mock Flask web application serving as a realistic test target for BDD/Behave + Playwright automation.

## Purpose

This app simulates a data analytics platform with KPI dashboards, anomaly detection, and root cause analysis (RCA) pages. It is designed to be tested by the BDD/Playwright framework in this project — all routes have `data-testid` attributes for reliable selector targeting.

## Architecture (two tiers, running in parallel)

The app is mid-migration from a server-rendered Flask UI to a React single-page
application that mirrors the work "ARC" stack (React 18 SPA on S3). Both tiers
currently run in parallel against the same data layer — nothing has been cut over
yet, so the Flask HTML UI is still fully functional.

- **Flask (`app.py`, `templates/`)** — the original server-rendered Jinja UI plus a
  new pure-JSON REST API blueprint (`api/`). Both are served by the same Flask
  process. The REST API is a thin wrapper over the shared, view-independent data
  layer (`data_source.py`) and is the foundation the SPA builds against.
- **React SPA (`frontend/`)** — a Vite + React 18 + TypeScript app (Redux Toolkit +
  RTK Query + React Router v6) consuming the REST API. See
  [`frontend/`](#react-spa-frontend) below.

The migration is tracked by the approved design doc at
`aws-lab/.agents/designs/ui-react-migration-design.md`. Completed so far: the REST
API carve-out, the React SPA (all pages, ARC stand-in component library, dashboard
charts, Cytoscape RCA graph), and the session-cookie auth flow. Still pending: the
Jinja cut-over (Flask serving the built SPA + retiring templates) and the CI build
step.

## Prerequisites

- Python 3.8 or higher
- pip

## Setup

```bash
cd mock-app
pip install -r requirements.txt
```

## Running

```bash
python run.py
```

The app will start at **http://localhost:5000**

## Test Credentials

Any non-empty username and password combination will work:

- Username: `testuser` (or any non-empty value)
- Password: `testpass` (or any non-empty value)

## Pages

| URL | Description |
|-----|-------------|
| `/login` | Login page — enter any username/password |
| `/dashboard` | KPI dashboard with 5 metrics and date filter |
| `/anomalies` | Anomaly list with severity filter and acknowledge action |
| `/rca` | Root cause analysis list with status filter |
| `/rca/<id>` | RCA detail with status update form |

## REST API (`/api`)

A pure-JSON API blueprint (`api/`) served by the same Flask process, consumed by the
React SPA. All data endpoints require an authenticated session cookie; the data layer
falls back to demo data on any backend error, so they do not 5xx on a lab outage.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/login` | Log in with `{username, password}` (any non-empty pair) |
| `GET` | `/api/session` | Current session: `{authenticated, user, mode, refresh_seconds}` |
| `POST` | `/api/logout` | Clear the session |
| `GET` | `/api/dashboard?date_from=&date_to=` | KPI list (exactly 5 KPIs) |
| `GET` | `/api/charts?date_from=&date_to=` | Dashboard chart datasets (by vendor / severity / over time) |
| `GET` | `/api/anomalies?severity=` | Anomaly list |
| `GET` | `/api/anomalies/<id>` | Single anomaly (`404` if absent) |
| `POST` | `/api/anomalies/<id>/acknowledge` | Acknowledge an anomaly |
| `GET` | `/api/rca?status=` | RCA record list |
| `GET` | `/api/rca/<id>` | Single RCA record (`404` if absent) |
| `POST` | `/api/rca/<id>/status` | Update RCA status (`{status}`; `400` on invalid) |
| `GET` | `/api/rca/<id>/graph` | RCA subgraph for the Cytoscape view (empty graph when unavailable) |

CORS is enabled for `/api/*` with credentials, scoped to the SPA origin via the
`SPA_ORIGIN` env var (default `http://localhost:3000`). This is only needed for a
two-origin setup; the recommended dev setup uses the Vite proxy (below) for a single
origin, so cookies work without CORS.

## React SPA (`frontend/`)

A Vite + React 18 + TypeScript single-page app (Redux Toolkit + RTK Query + React
Router v6) built against the REST API, approximating the work "ARC" stack. ARC itself
is proprietary and cannot be installed here, so the SPA uses a home-grown stand-in
component library under `src/components/arc/` (imported via the `@arc` alias) with clean
prop contracts so the real ARC could drop in later.

Highlights:

- Mirrors the Flask routes (`/login`, `/dashboard`, `/anomalies`, `/anomalies/:id`,
  `/rca`, `/rca/:id`, `/ingestion`) and reproduces the same `data-testid` values so the
  existing BDD page objects keep working after cut-over.
- Dashboard charts via `react-chartjs-2`; the RCA detail graph via `react-cytoscapejs`
  (both the same underlying libraries the Flask app vendored).
- Session-cookie auth: `credentials: 'include'`, session rehydrate on reload, and a
  global 401 handler that returns to the login page on session expiry.
- Live-mode refresh is handled by RTK Query polling (driven by the `/api/session`
  `mode`/`refresh_seconds` fields) behind a `useLivePolling` seam — the swap-in point
  for a future WebSocket channel.

### Running the SPA (dev)

The SPA needs the Flask API running (for `/api`), then the Vite dev server proxies
`/api` to Flask on `:5000` so the session cookie works single-origin.

```powershell
# 1. Start the Flask API (serves /api + the legacy HTML UI) in one terminal:
cd mock-app
python run.py            # http://localhost:5000

# 2. In another terminal, start the SPA dev server:
cd mock-app\frontend
$env:NODE_OPTIONS="--use-system-ca"   # required behind the corporate TLS proxy
npm install
npm run dev              # Vite prints the dev URL; it proxies /api -> http://localhost:5000
```

Open the URL Vite prints (Vite's default dev port is `5173`). Because the dev server
proxies `/api` to Flask, the browser sees a single origin and the session cookie works
without CORS. The `SPA_ORIGIN` CORS variable is only needed if you instead serve the SPA
from a separate origin and talk to Flask cross-origin.

> **Corporate-proxy note:** `NODE_OPTIONS=--use-system-ca` is required for `npm install`
> and any `npx`/Vite command on the proxied network, or they fail with TLS cert errors.

### npm scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Vite dev server with the `/api` → Flask proxy |
| `npm run build` | Type-check (`tsc --noEmit`) + production build to `frontend/dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run test` | Run the Vitest unit suite |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | `dev-secret-key-change-in-production` | Session signing key — **change this in production** |
| `SPA_ORIGIN` | `http://localhost:3000` | Allowed CORS origin for `/api/*` (two-origin setup only; the Vite proxy avoids needing this) |

## AWS lab integration (live data)

By default the app serves its built-in demo data and needs only Flask. You can
optionally point it at the local AWS lab (LocalStack S3 + Postgres) to serve
live anomaly scores and RCA results instead.

Set `LAB_DATA_SOURCE=live` to enable live mode. In live mode the app reads
anomaly scores from the lab S3 bucket (`pm-anomaly-scores`) and RCA results
from the lab Postgres database. If the lab is unreachable or any read fails,
the app automatically falls back to the built-in demo data and logs a warning —
it never errors out, so live mode is always safe to leave on.

`demo` is the default; when `LAB_DATA_SOURCE` is unset the app behaves exactly
as it did before (in-memory demo data, UI changes reset on restart). The
`boto3` and `pg8000` dependencies are only used by live mode.

| Variable | Default | Description |
|----------|---------|-------------|
| `LAB_DATA_SOURCE` | `demo` | `demo` (built-in data) or `live` (read from the lab) |
| `LAB_S3_ENDPOINT` | `http://localhost:4566` | LocalStack S3 endpoint for anomaly scores |
| `LAB_PG_HOST` | `localhost` | RCA Postgres host |
| `LAB_PG_PORT` | `5432` | RCA Postgres port |
| `LAB_PG_DB` | `rca` | RCA Postgres database name |
| `LAB_PG_USER` | `rca` | RCA Postgres user |
| `LAB_PG_PASSWORD` | `rca` | RCA Postgres password |
| `AWS_ACCESS_KEY_ID` | `test` | LocalStack dummy access key |
| `AWS_SECRET_ACCESS_KEY` | `test` | LocalStack dummy secret key |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region for the S3 client |

Example (PowerShell):

```powershell
$env:LAB_DATA_SOURCE='live'
$env:LAB_S3_ENDPOINT='http://localhost:4566'
$env:LAB_PG_HOST='localhost'
$env:LAB_PG_PORT='5432'
$env:LAB_PG_DB='rca'
$env:LAB_PG_USER='rca'
$env:LAB_PG_PASSWORD='rca'
$env:AWS_ACCESS_KEY_ID='test'
$env:AWS_SECRET_ACCESS_KEY='test'
$env:AWS_DEFAULT_REGION='us-east-1'
python run.py
```

To return to demo mode, clear the variable: `Remove-Item Env:LAB_DATA_SOURCE`.

### Auto-refresh (live mode only)

When `LAB_DATA_SOURCE=live`, the `/dashboard`, `/anomalies`, and `/rca` pages emit a
`<meta http-equiv="refresh">` tag so they auto-refresh and pick up newly arriving live data.
`LIVE_REFRESH_SECONDS` (default `5`) controls the interval.

In demo mode (the default, `LAB_DATA_SOURCE` unset) no refresh directive is rendered and the pages
are **byte-for-byte unchanged** from before this feature.

| Variable | Default | Description |
|----------|---------|-------------|
| `LIVE_REFRESH_SECONDS` | `5` | Auto-refresh interval in seconds for the dashboard/anomalies/RCA pages — live mode only. |

### RCA subgraph visual (live mode only)

In live mode, `GET /rca/<id>` renders a node-link diagram of that record's RCA subgraph
beneath the detail panel: the anomaly, its root cause (via the `caused_by` edge) and any
correlated incident/change (via the `correlates_with` edge). The diagram is drawn client-side
with a **vendored** copy of Cytoscape.js (`static/vendor/cytoscape.min.js`) — there is **no CDN
request at runtime** — and its data is inlined into the page as JSON (no extra HTTP endpoint).

The app resolves the UI id to the lab `rca_id` and reads the subgraph from the local Gremlin
server (swappable for managed Amazon Neptune by changing `GREMLIN_URL` only). If Gremlin is
unreachable, the id does not resolve, or the subgraph is empty, the page fails safe to a
"Graph unavailable" placeholder and still returns HTTP 200 — it never errors out.

In **demo mode** (the default, `LAB_DATA_SOURCE` unset) none of this renders: no graph panel,
no placeholder, no new `data-testid`, no `<script>`. The `/rca/<id>` page is **byte-for-byte
unchanged** from before this feature (locked by `tests/test_demo_byte_compat.py`). The
`gremlinpython` dependency is imported lazily inside the live read path only, so demo-mode
imports stay Flask-only.

| Variable | Default | Description |
|----------|---------|-------------|
| `GREMLIN_URL` | `ws://localhost:8182/gremlin` | Gremlin/Neptune WebSocket endpoint for the live RCA subgraph read — live mode only. |

## Notes

- All data is held in-memory. Restarting the server resets any changes made via the UI.
- The dashboard date filter returns an empty state when `date_to` year is after 2030 — useful for testing empty-state scenarios.
- The app runs in Flask debug mode by default when started via `run.py`. Do not use debug mode in production.
