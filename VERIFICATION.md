# Verification — LIVE-mode RCA title includes window_start

## Change
LIVE mode only: in `data_source.py` `map_rca_rows`, the RCA `title` value changed from
`"{vendor} {anomaly_metric} RCA"` to `"{vendor} {anomaly_metric} @ {window_start}"`
(e.g. `vendor_c rrc_conn_count @ 2026-10-17T05:25:00Z`). `window_start` was already read as
the sort key; it is now bound as a loop local and used in the title. No keys added/removed
(RCA keys remain `id, title, status, root_cause, recommendation`). `map_anomaly_scores`, the
`DEMO_RCA`/`DEMO_ANOMALIES` constants, routes, templates, data-testids, and JSON shapes were
not touched.

## 1. Unit tests
Command: `cd c:\Users\acoak\.kiro\projects\mock-app ; python -m pytest tests/ -q`
Result: **10 passed in 0.03s**

Updated/added tests in `tests/test_data_source_mapping.py`:
- `test_map_rca_rows_title_and_root_cause` → asserts `'acme latency @ w1'`.
- `test_map_rca_rows_confidence_status` → status lookups keyed by new titles `acme a @ w1`,
  `acme b @ w2`, `acme c @ w3`.
- NEW `test_map_rca_rows_distinct_window_titles` → two rows with same vendor+metric
  (`vendor_c`/`rrc_conn_count`) at windows `2026-10-17T05:20:00Z` and `2026-10-17T06:20:00Z`
  assert the two titles are DISTINCT and each contains its own `window_start`.
- NEW `test_map_rca_rows_keys_unchanged` → RCA dict keys are exactly
  `{id, title, status, root_cause, recommendation}`.
- NEW `test_get_rca_records_demo_titles_unchanged` → demo mode (no `LAB_DATA_SOURCE`) returns
  the fixed `DEMO_RCA` titles unchanged.

## 2. Demo byte-compatibility
Rendered `/dashboard`, `/anomalies`, `/rca` HTML and `/api/anomalies`, `/api/rca` JSON from the
pre-change `data_source.py` (via `git show HEAD:data_source.py`) and from the current code, both
through the Flask test client in demo mode (no `LAB_DATA_SOURCE`), then compared SHA-256 hashes.
Result: **all 5 outputs IDENTICAL** (dashboard.html, anomalies.html, rca.html,
api_anomalies.json, api_rca.json). Demo output is byte-for-byte unchanged.

## 3. BDD regression (demo mode on :5000)
Command: `cd c:\Users\acoak\.kiro\projects\bdd-framework ; behave --tags="~skip"`
(app started with no `LAB_DATA_SOURCE`, confirmed `GET /` → 200).
Result: **6 features passed, 0 failed; 29 scenarios passed, 0 failed, 1 skipped;
112 steps passed, 0 failed.** `bdd-framework/.env` was neither read nor modified.

## 4. Live behavior
Lab Postgres `rca_results` had **1 row** (it was just truncated). With `LAB_DATA_SOURCE=live`,
`get_rca_records()` returned
`'vendor_c rrc_conn_count @ 2026-10-17T05:25:00Z'` with keys
`['id','recommendation','root_cause','status','title']` — confirming the new live title format
and unchanged keys. Because only one live row exists, the distinct-title (disambiguation) case
is covered by the `test_map_rca_rows_distinct_window_titles` unit test, which is sufficient
evidence per the plan.

## 5. Cleanup
Background `python run.py` processes were stopped; temporary verification files were removed.
`LAB_DATA_SOURCE` was unset at the end.
