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

## Notes

- All data is held in-memory. Restarting the server resets any changes made via the UI.
- The dashboard date filter returns an empty state when `date_to` year is after 2030 — useful for testing empty-state scenarios.
- The app runs in Flask debug mode by default when started via `run.py`. Do not use debug mode in production.
