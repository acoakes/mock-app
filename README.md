# Mock Data Analytics Platform

A mock Flask web application serving as a realistic test target for BDD/Behave + Playwright automation.

## Purpose

This app simulates a data analytics platform with KPI dashboards, anomaly detection, and root cause analysis (RCA) pages. It is designed to be tested by the BDD/Playwright framework in this project — all routes have `data-testid` attributes for reliable selector targeting.

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

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | `dev-secret-key-change-in-production` | Session signing key — **change this in production** |

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
