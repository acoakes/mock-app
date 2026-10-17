# Verification — LIVE-mode-only RCA subgraph visual (Part 2, AC-8..AC-12)

## Change
Live-mode-only: `GET /rca/<id>` now renders a client-side Cytoscape node-link diagram of the
record's RCA subgraph (anomaly → root_cause via `caused_by`; incident/change → anomaly via
`correlates_with`), drawn from a **vendored** `static/vendor/cytoscape.min.js` (Cytoscape
3.30.4, no CDN at runtime) with the `{nodes, edges}` payload inlined as `<script
type="application/json" id="rca-graph-data">` (no new HTTP endpoint). `static/rca_graph.js`
parses that JSON and builds the graph (node coloured by `ntype`, edge labelled by `etype`).

- `rca_graph_client.py` (new): a self-contained `gremlinpython` reader whose `get_rca_chain`
  re-implements FEAT-001's `{nodes, edges}` wire contract (gid→id, ntype→type, label→label,
  rest→props; edge label→type, out gid→from, in gid→to; native `.out('caused_by')` /
  `.in_('correlates_with')` direction). Raises `ConnectionError` when Gremlin is unreachable.
- `data_source.py`: `map_rca_rows(rows, include_rca_id=False)` — default keeps the exact demo
  key set `{id, title, status, root_cause, recommendation}`; `_read_live_rca()` passes
  `include_rca_id=True`. New `_resolve_rca_id(ui_id)` (scan `get_rca_records()`) and
  `get_rca_subgraph(ui_id)` (None in demo; resolve id → lazy-import `rca_graph_client` → fetch;
  any exception ⇒ log warning + return None, fail-safe FR-13).
- `app.py` `rca_detail(id)`: computes `live_mode`, sets `rca_graph =
  data_source.get_rca_subgraph(id) if live_mode else None`, passes both to the template.
- `templates/rca_detail.html`: a single whitespace-trimmed `{%- if live_mode %} ... {%- endif
  %}` block inserted between the detail-panel `</div>` and `{% endblock %}`. Inside:
  `{% if rca_graph and rca_graph.nodes %}` → `rca-graph-panel` + diagram + vendored scripts,
  `{% else %}` → `rca-graph-unavailable` placeholder. **Guard decision:** the outer guard is
  `live_mode` alone (not `live_mode and rca_graph`) so that in live mode BOTH a `None` subgraph
  (Gremlin down) and an empty subgraph render the placeholder — satisfying AC-11 — while demo
  mode (`live_mode` False) still collapses the whole block to nothing, keeping demo bytes
  byte-identical. This resolves a §7.1-vs-AC-11 contradiction in the design; approved before
  implementation.
- `static/style.css`: added a `.rca-graph` container rule (height/border). CSS is a separate
  asset; the `/rca`, `/rca/1`, `/api/rca` response bytes are unaffected.
- `requirements.txt`: added `gremlinpython==3.7.2` (+ `async_timeout==4.0.3`, the aiohttp
  transport runtime dep), imported lazily on the live path only.

The demo byte baseline in `tests/fixtures/demo_baseline/{rca.html,rca_1.html,api_rca.json}` was
captured from the **unmodified** app (LAB_DATA_SOURCE unset) BEFORE any template/data_source
edit, and is committed as the authority for the byte-compat gate.

## 1. Unit suite + byte-compat gate (AC-8)
Command: `cd c:\Users\acoak\.kiro\projects\mock-app ; python -m pytest tests/ -q`
Result: **19 passed in 0.13s**

Includes the pre-existing mapping tests (10, all still green incl.
`test_map_rca_rows_keys_unchanged` and `test_get_rca_records_demo_titles_unchanged`), the new
resolver/fail-safe tests, and `tests/test_demo_byte_compat.py`, which asserts the raw bytes of
`GET /rca`, `GET /rca/1`, `GET /api/rca` in demo mode equal the committed
`tests/fixtures/demo_baseline/` files. Any diff is a HARD failure (NFR-1/AC-8/MEDIUM-4).

## 2. Lazy import — demo path is Flask-only (AC #7)
Command: `python -c "import sys; import data_source, app, rca_graph_client; assert
'gremlin_python' not in sys.modules; print('OK')"`
Result: **OK: imports clean, gremlin_python not loaded at module level.** `gremlinpython` is
imported only inside `get_rca_subgraph`'s live branch.

## 3. Demo-mode BDD regression (AC-9)
App started in demo mode (`LAB_DATA_SOURCE` unset) on :5000 (`GET /` → 302 to login confirmed).
Command: `cd c:\Users\acoak\.kiro\projects\bdd-framework ; behave --tags="~skip"`
Result: **6 features passed, 0 failed, 0 skipped; 29 scenarios passed, 0 failed, 1 skipped;
112 steps passed, 0 failed, 3 skipped, 0 undefined. Took 1m45s.** No files in `bdd-framework`
were edited and `bdd-framework/.env` was never read or modified.

## 4. Live render + fail-safe placeholder (AC-10/AC-11/AC-12)
With `LAB_DATA_SOURCE=live`, driving `data_source.get_rca_subgraph` through the Flask test
client (logged-in session):

- **A — populated subgraph** (anomaly:9, root_cause:9, incident:INC-1 with `caused_by` +
  `correlates_with` edges): `GET /rca/1` → **HTTP 200**, page contains
  `data-testid="rca-graph-panel"`, references the vendored
  `static/vendor/cytoscape.min.js` + `static/rca_graph.js`, and contains **no** CDN
  reference (`unpkg`/`cdn` absent). All three node types present (AC-10/AC-12).
- **B — Gremlin unreachable** (`get_rca_subgraph` returns None): `GET /rca/1` → **HTTP 200**
  (never 500), page shows the `data-testid="rca-graph-unavailable"` placeholder (AC-11/FR-13).
- **C — empty subgraph** (`{"nodes": [], "edges": []}`): `GET /rca/1` → **HTTP 200**, same
  `rca-graph-unavailable` placeholder (AC-11).

The vendored asset is Cytoscape 3.30.4 (373,734 bytes; banner "Copyright (c) 2016-2024, The
Cytoscape Consortium."). A manual against-a-live-Gremlin render was not run in this step (no
Gremlin container was started here); the end-to-end live path is otherwise exercised by the
above test-client drive of the route + template. The id→rca_id resolver and the fail-safe
(None ⇒ placeholder) are covered by unit tests in `tests/test_data_source_mapping.py`.

## 5. Cleanup
The background `python run.py` (demo mode) started for the BDD run was stopped. No temp files
were left in the repo (`git status` shows only the intended FEAT-002 paths). `LAB_DATA_SOURCE`
was left unset.
