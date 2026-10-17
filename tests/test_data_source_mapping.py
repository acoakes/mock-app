"""Pure-mapping unit tests for data_source.

These tests use hand-built dict fixtures only; they never touch S3 or Postgres.
"""

import data_source


# ---------------------------------------------------------------------------
# map_anomaly_scores
# ---------------------------------------------------------------------------
def test_map_anomaly_scores_drops_non_anomalies():
    records = [
        {'vendor': 'acme', 'region': 'eu-west', 'site': 'site-0001', 'metric': 'latency', 'window_start': '2024-01-01T00:00', 'mean': 1.0, 'score': 2.5, 'is_anomaly': True, 'method': 'zscore'},
        {'vendor': 'acme', 'region': 'eu-west', 'site': 'site-0001', 'metric': 'latency', 'window_start': '2024-01-01T01:00', 'mean': 1.0, 'score': 0.5, 'is_anomaly': False, 'method': 'zscore'},
    ]
    result = data_source.map_anomaly_scores(records)
    assert len(result) == 1
    assert result[0]['timestamp'] == '2024-01-01T00:00'


def test_map_anomaly_scores_severity_boundaries():
    records = [
        {'vendor': 'v', 'region': 'r', 'site': 's', 'metric': 'm', 'window_start': 'w1', 'score': 3.0, 'is_anomaly': True},
        {'vendor': 'v', 'region': 'r', 'site': 's', 'metric': 'm', 'window_start': 'w2', 'score': 2.0, 'is_anomaly': True},
        {'vendor': 'v', 'region': 'r', 'site': 's', 'metric': 'm', 'window_start': 'w3', 'score': 1.5, 'is_anomaly': True},
        {'vendor': 'v', 'region': 'r', 'site': 's', 'metric': 'm', 'window_start': 'w4', 'score': -3.5, 'is_anomaly': True},
    ]
    result = data_source.map_anomaly_scores(records)
    by_ts = {r['timestamp']: r['severity'] for r in result}
    assert by_ts['w1'] == 'HIGH'
    assert by_ts['w2'] == 'MEDIUM'
    assert by_ts['w3'] == 'LOW'
    assert by_ts['w4'] == 'HIGH'


def test_map_anomaly_scores_description_and_timestamp():
    records = [
        {'vendor': 'acme', 'region': 'eu-west', 'site': 'site-0142', 'metric': 'latency', 'window_start': '2024-01-01T00:00', 'score': 2.345, 'is_anomaly': True},
    ]
    result = data_source.map_anomaly_scores(records)
    assert result[0]['description'] == 'acme/site-0142 (eu-west): latency anomaly (z=2.35) at 2024-01-01T00:00'
    assert result[0]['timestamp'] == '2024-01-01T00:00'
    assert result[0]['status'] == 'open'


def test_map_anomaly_scores_ids_are_one_based_and_stable_after_sort():
    records = [
        {'vendor': 'bravo', 'region': 'r', 'site': 's', 'metric': 'm', 'window_start': 'w1', 'score': 2.1, 'is_anomaly': True},
        {'vendor': 'acme', 'region': 'r', 'site': 's', 'metric': 'm', 'window_start': 'w2', 'score': 2.1, 'is_anomaly': True},
        {'vendor': 'acme', 'region': 'r', 'site': 's', 'metric': 'm', 'window_start': 'w1', 'score': 2.1, 'is_anomaly': True},
    ]
    result = data_source.map_anomaly_scores(records)
    assert [r['id'] for r in result] == [1, 2, 3]
    # sorted by (vendor, region, site, window_start): acme/w1, acme/w2, bravo/w1
    assert [(r['id'], r['timestamp']) for r in result] == [(1, 'w1'), (2, 'w2'), (3, 'w1')]
    assert result[0]['description'].startswith('acme/')
    assert result[2]['description'].startswith('bravo/')


# ---------------------------------------------------------------------------
# map_rca_rows
# ---------------------------------------------------------------------------
def test_map_rca_rows_title_and_root_cause():
    rows = [
        {'rca_id': 10, 'vendor': 'acme', 'region': 'eu-west', 'site': 'site-0142', 'window_start': 'w1', 'anomaly_metric': 'latency', 'correlated_incident_id': None, 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'network blip'},
    ]
    result = data_source.map_rca_rows(rows)
    assert result[0]['title'] == 'acme/site-0142 latency @ w1'
    assert result[0]['root_cause'] == 'network blip'
    assert result[0]['id'] == 1


def test_map_rca_rows_recommendation_change_vs_fault():
    rows = [
        {'rca_id': 1, 'vendor': 'acme', 'window_start': 'w1', 'anomaly_metric': 'cpu', 'correlated_change_id': 'CHG-42', 'confidence': 0.9, 'predicted_root_cause': 'bad deploy'},
        {'rca_id': 2, 'vendor': 'acme', 'window_start': 'w2', 'anomaly_metric': 'cpu', 'correlated_change_id': None, 'confidence': 0.4, 'predicted_root_cause': 'hw fault'},
    ]
    result = data_source.map_rca_rows(rows)
    assert result[0]['recommendation'] == 'Review and consider rolling back change CHG-42'
    assert result[1]['recommendation'] == 'Investigate as a genuine fault (no correlated change).'


def test_map_rca_rows_confidence_status():
    rows = [
        {'rca_id': 1, 'vendor': 'acme', 'region': 'r', 'site': 'site-0142', 'window_start': 'w1', 'anomaly_metric': 'a', 'correlated_change_id': None, 'confidence': 0.8, 'predicted_root_cause': 'x'},
        {'rca_id': 2, 'vendor': 'acme', 'region': 'r', 'site': 'site-0142', 'window_start': 'w2', 'anomaly_metric': 'b', 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'y'},
        {'rca_id': 3, 'vendor': 'acme', 'region': 'r', 'site': 'site-0142', 'window_start': 'w3', 'anomaly_metric': 'c', 'correlated_change_id': None, 'confidence': None, 'predicted_root_cause': 'z'},
    ]
    result = data_source.map_rca_rows(rows)
    status_by_title = {r['title']: r['status'] for r in result}
    assert status_by_title['acme/site-0142 a @ w1'] == 'in_progress'
    assert status_by_title['acme/site-0142 b @ w2'] == 'open'
    assert status_by_title['acme/site-0142 c @ w3'] == 'open'


def test_map_rca_rows_distinct_window_titles():
    """Same vendor+metric at different windows must yield distinct titles."""
    rows = [
        {'rca_id': 1, 'vendor': 'vendor_c', 'window_start': '2026-10-17T05:20:00Z', 'anomaly_metric': 'rrc_conn_count', 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'x'},
        {'rca_id': 2, 'vendor': 'vendor_c', 'window_start': '2026-10-17T06:20:00Z', 'anomaly_metric': 'rrc_conn_count', 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'y'},
    ]
    result = data_source.map_rca_rows(rows)
    titles = [r['title'] for r in result]
    assert titles[0] != titles[1]
    assert '2026-10-17T05:20:00Z' in titles[0]
    assert '2026-10-17T06:20:00Z' in titles[1]


def test_map_rca_rows_keys_unchanged():
    rows = [
        {'rca_id': 1, 'vendor': 'acme', 'window_start': 'w1', 'anomaly_metric': 'latency', 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'x'},
    ]
    result = data_source.map_rca_rows(rows)
    assert set(result[0].keys()) == {'id', 'title', 'status', 'root_cause', 'recommendation'}


def test_get_rca_records_demo_titles_unchanged():
    """Demo mode (no LAB_DATA_SOURCE) must return the fixed DEMO_RCA titles."""
    titles = [r['title'] for r in data_source.get_rca_records()]
    assert titles == [
        'Null Value Spike Root Cause',
        'Latency Threshold Breach Analysis',
        'Duplicate Record Investigation',
        'Revenue Field Data Quality Issue',
    ]


# ---------------------------------------------------------------------------
# map_rca_rows include_rca_id (live-only key)
# ---------------------------------------------------------------------------
def test_map_rca_rows_include_rca_id_adds_key():
    rows = [
        {'rca_id': 77, 'vendor': 'acme', 'window_start': 'w1', 'anomaly_metric': 'latency', 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'x'},
    ]
    result = data_source.map_rca_rows(rows, include_rca_id=True)
    assert set(result[0].keys()) == {'id', 'title', 'status', 'root_cause', 'recommendation', 'rca_id'}
    assert result[0]['rca_id'] == 77


def test_map_rca_rows_default_omits_rca_id():
    rows = [
        {'rca_id': 77, 'vendor': 'acme', 'window_start': 'w1', 'anomaly_metric': 'latency', 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'x'},
    ]
    result = data_source.map_rca_rows(rows)
    assert set(result[0].keys()) == {'id', 'title', 'status', 'root_cause', 'recommendation'}


# ---------------------------------------------------------------------------
# _resolve_rca_id
# ---------------------------------------------------------------------------
def test_resolve_rca_id_returns_matching_rca_id(monkeypatch):
    fake_live = [
        {'id': 1, 'title': 't1', 'status': 'open', 'root_cause': 'r', 'recommendation': 'x', 'rca_id': 101},
        {'id': 2, 'title': 't2', 'status': 'open', 'root_cause': 'r', 'recommendation': 'x', 'rca_id': 202},
    ]
    monkeypatch.setattr(data_source, 'get_rca_records', lambda: fake_live)
    assert data_source._resolve_rca_id(2) == 202


def test_resolve_rca_id_out_of_range_returns_none(monkeypatch):
    fake_live = [
        {'id': 1, 'title': 't1', 'status': 'open', 'root_cause': 'r', 'recommendation': 'x', 'rca_id': 101},
    ]
    monkeypatch.setattr(data_source, 'get_rca_records', lambda: fake_live)
    assert data_source._resolve_rca_id(99) is None


# ---------------------------------------------------------------------------
# get_rca_subgraph (fail-safe)
# ---------------------------------------------------------------------------
def test_get_rca_subgraph_demo_mode_returns_none(monkeypatch):
    monkeypatch.delenv('LAB_DATA_SOURCE', raising=False)
    assert data_source.get_rca_subgraph(1) is None


def test_get_rca_subgraph_fail_safe_on_client_error(monkeypatch):
    monkeypatch.setenv('LAB_DATA_SOURCE', 'live')
    monkeypatch.setattr(data_source, '_resolve_rca_id', lambda ui_id: 101)

    import rca_graph_client

    def _boom(rca_id):
        raise ConnectionError('gremlin down')

    monkeypatch.setattr(rca_graph_client, 'get_rca_chain', _boom)
    assert data_source.get_rca_subgraph(1) is None


# ---------------------------------------------------------------------------
# REVIEW-7: demo mode must NEVER route through the live mappers
# ---------------------------------------------------------------------------
def test_demo_mode_never_routes_through_mappers(monkeypatch):
    """Demo reads must return deep copies of the DEMO_* constants without ever
    calling map_rca_rows / map_anomaly_scores. Patch both mappers to raise; if
    demo mode routed through either, these reads would blow up."""
    monkeypatch.delenv('LAB_DATA_SOURCE', raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError('demo mode must not call the live mapper')

    monkeypatch.setattr(data_source, 'map_rca_rows', _boom)
    monkeypatch.setattr(data_source, 'map_anomaly_scores', _boom)

    rca = data_source.get_rca_records()
    anomalies = data_source.get_anomalies()

    assert rca == data_source.DEMO_RCA
    assert anomalies == data_source.DEMO_ANOMALIES
    # deep copies, not the module constants / per-process stores
    assert rca is not data_source.DEMO_RCA
    assert rca is not data_source._demo_rca
    assert anomalies is not data_source.DEMO_ANOMALIES
    assert anomalies is not data_source._demo_anomalies
