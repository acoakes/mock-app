"""Pure-mapping unit tests for data_source.

These tests use hand-built dict fixtures only; they never touch S3 or Postgres.
"""

import data_source


# ---------------------------------------------------------------------------
# map_anomaly_scores
# ---------------------------------------------------------------------------
def test_map_anomaly_scores_drops_non_anomalies():
    records = [
        {'vendor': 'acme', 'metric': 'latency', 'window_start': '2024-01-01T00:00', 'mean': 1.0, 'score': 2.5, 'is_anomaly': True, 'method': 'zscore'},
        {'vendor': 'acme', 'metric': 'latency', 'window_start': '2024-01-01T01:00', 'mean': 1.0, 'score': 0.5, 'is_anomaly': False, 'method': 'zscore'},
    ]
    result = data_source.map_anomaly_scores(records)
    assert len(result) == 1
    assert result[0]['timestamp'] == '2024-01-01T00:00'


def test_map_anomaly_scores_severity_boundaries():
    records = [
        {'vendor': 'v', 'metric': 'm', 'window_start': 'w1', 'score': 3.0, 'is_anomaly': True},
        {'vendor': 'v', 'metric': 'm', 'window_start': 'w2', 'score': 2.0, 'is_anomaly': True},
        {'vendor': 'v', 'metric': 'm', 'window_start': 'w3', 'score': 1.5, 'is_anomaly': True},
        {'vendor': 'v', 'metric': 'm', 'window_start': 'w4', 'score': -3.5, 'is_anomaly': True},
    ]
    result = data_source.map_anomaly_scores(records)
    by_ts = {r['timestamp']: r['severity'] for r in result}
    assert by_ts['w1'] == 'HIGH'
    assert by_ts['w2'] == 'MEDIUM'
    assert by_ts['w3'] == 'LOW'
    assert by_ts['w4'] == 'HIGH'


def test_map_anomaly_scores_description_and_timestamp():
    records = [
        {'vendor': 'acme', 'metric': 'latency', 'window_start': '2024-01-01T00:00', 'score': 2.345, 'is_anomaly': True},
    ]
    result = data_source.map_anomaly_scores(records)
    assert result[0]['description'] == 'acme: latency anomaly (z=2.35) at 2024-01-01T00:00'
    assert result[0]['timestamp'] == '2024-01-01T00:00'
    assert result[0]['status'] == 'open'


def test_map_anomaly_scores_ids_are_one_based_and_stable_after_sort():
    records = [
        {'vendor': 'bravo', 'metric': 'm', 'window_start': 'w1', 'score': 2.1, 'is_anomaly': True},
        {'vendor': 'acme', 'metric': 'm', 'window_start': 'w2', 'score': 2.1, 'is_anomaly': True},
        {'vendor': 'acme', 'metric': 'm', 'window_start': 'w1', 'score': 2.1, 'is_anomaly': True},
    ]
    result = data_source.map_anomaly_scores(records)
    assert [r['id'] for r in result] == [1, 2, 3]
    # sorted by (vendor, window_start): acme/w1, acme/w2, bravo/w1
    assert [(r['id'], r['timestamp']) for r in result] == [(1, 'w1'), (2, 'w2'), (3, 'w1')]
    assert result[0]['description'].startswith('acme:')
    assert result[2]['description'].startswith('bravo:')


# ---------------------------------------------------------------------------
# map_rca_rows
# ---------------------------------------------------------------------------
def test_map_rca_rows_title_and_root_cause():
    rows = [
        {'rca_id': 10, 'vendor': 'acme', 'window_start': 'w1', 'anomaly_metric': 'latency', 'correlated_incident_id': None, 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'network blip'},
    ]
    result = data_source.map_rca_rows(rows)
    assert result[0]['title'] == 'acme latency @ w1'
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
        {'rca_id': 1, 'vendor': 'acme', 'window_start': 'w1', 'anomaly_metric': 'a', 'correlated_change_id': None, 'confidence': 0.8, 'predicted_root_cause': 'x'},
        {'rca_id': 2, 'vendor': 'acme', 'window_start': 'w2', 'anomaly_metric': 'b', 'correlated_change_id': None, 'confidence': 0.5, 'predicted_root_cause': 'y'},
        {'rca_id': 3, 'vendor': 'acme', 'window_start': 'w3', 'anomaly_metric': 'c', 'correlated_change_id': None, 'confidence': None, 'predicted_root_cause': 'z'},
    ]
    result = data_source.map_rca_rows(rows)
    status_by_title = {r['title']: r['status'] for r in result}
    assert status_by_title['acme a @ w1'] == 'in_progress'
    assert status_by_title['acme b @ w2'] == 'open'
    assert status_by_title['acme c @ w3'] == 'open'


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
