"""Data-access module for the mock-app.

Exposes get_anomalies() / get_rca_records() plus pure mapping functions and
lab live readers (S3 jsonl for anomaly scores, Postgres via pg8000 for RCA
results). Live mode is opt-in via the LAB_DATA_SOURCE=live env var and always
falls back to demo data on any failure, so the app never depends on the lab.

boto3 and pg8000 are imported lazily inside the live code paths so this module
imports cleanly with only Flask installed.
"""

import copy
import json
import logging
import os

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Demo data (copied verbatim from app.py module-level lists)
# ---------------------------------------------------------------------------
DEMO_ANOMALIES = [
    {'id': 1, 'description': 'Spike in null values in field user_id', 'severity': 'HIGH', 'status': 'open', 'timestamp': '2024-01-15 14:32:01'},
    {'id': 2, 'description': 'Processing latency exceeded threshold', 'severity': 'MEDIUM', 'status': 'acknowledged', 'timestamp': '2024-01-15 13:20:45'},
    {'id': 3, 'description': 'Duplicate records detected in batch 4821', 'severity': 'HIGH', 'status': 'open', 'timestamp': '2024-01-15 12:05:12'},
    {'id': 4, 'description': 'Missing values in revenue field', 'severity': 'LOW', 'status': 'open', 'timestamp': '2024-01-14 09:44:33'},
    {'id': 5, 'description': 'Schema mismatch in incoming data feed', 'severity': 'MEDIUM', 'status': 'acknowledged', 'timestamp': '2024-01-14 08:15:20'},
]

DEMO_RCA = [
    {'id': 1, 'title': 'Null Value Spike Root Cause', 'status': 'resolved', 'root_cause': 'Upstream data pipeline failed validation step', 'recommendation': 'Add validation checkpoint at ingestion layer'},
    {'id': 2, 'title': 'Latency Threshold Breach Analysis', 'status': 'in_progress', 'root_cause': 'Database query not using index on timestamp column', 'recommendation': 'Add composite index on (timestamp, batch_id)'},
    {'id': 3, 'title': 'Duplicate Record Investigation', 'status': 'open', 'root_cause': 'Idempotency key not enforced in batch processor', 'recommendation': 'Implement idempotency enforcement in batch processing module'},
    {'id': 4, 'title': 'Revenue Field Data Quality Issue', 'status': 'open', 'root_cause': 'Source system sending null for optional revenue field', 'recommendation': 'Add default value handling and source system notification'},
]


# ---------------------------------------------------------------------------
# Per-process status overlays for live-mode mutations (int-keyed)
# ---------------------------------------------------------------------------
_anomaly_status_overlay = {}
_rca_status_overlay = {}


def set_anomaly_status(id, status):
    """Record a live-mode status override for the anomaly with the given id."""
    _anomaly_status_overlay[int(id)] = status


def set_rca_status(id, status):
    """Record a live-mode status override for the RCA record with the given id."""
    _rca_status_overlay[int(id)] = status


# ---------------------------------------------------------------------------
# Pure mapping functions (no I/O)
# ---------------------------------------------------------------------------
def map_anomaly_scores(records):
    """Map raw lab anomaly-score records to UI anomaly dicts.

    Keeps only records where is_anomaly is true, sorts by (vendor,
    window_start), assigns 1-based ids by position and synthesises the UI
    fields. Severity is derived from abs(score).
    """
    kept = [r for r in records if r.get('is_anomaly')]
    kept = sorted(kept, key=lambda r: (r.get('vendor'), r.get('window_start')))
    result = []
    for idx, r in enumerate(kept, start=1):
        vendor = r.get('vendor')
        metric = r.get('metric')
        score = r.get('score')
        window_start = r.get('window_start')
        magnitude = abs(score)
        if magnitude >= 3.0:
            severity = 'HIGH'
        elif magnitude >= 2.0:
            severity = 'MEDIUM'
        else:
            severity = 'LOW'
        result.append({
            'id': idx,
            'description': "{}: {} anomaly (z={:.2f}) at {}".format(vendor, metric, score, window_start),
            'severity': severity,
            'status': 'open',
            'timestamp': window_start,
        })
    return result


def map_rca_rows(rows):
    """Map raw lab rca_results rows (as dicts) to UI RCA record dicts.

    Orders by (vendor, window_start, anomaly_metric), assigns 1-based ids by
    position and synthesises the UI fields.
    """
    ordered = sorted(
        rows,
        key=lambda r: (r.get('vendor'), r.get('window_start'), r.get('anomaly_metric')),
    )
    result = []
    for idx, r in enumerate(ordered, start=1):
        vendor = r.get('vendor')
        anomaly_metric = r.get('anomaly_metric')
        confidence = r.get('confidence')
        correlated_change_id = r.get('correlated_change_id')
        status = 'in_progress' if confidence is not None and confidence >= 0.8 else 'open'
        if correlated_change_id:
            recommendation = "Review and consider rolling back change {}".format(correlated_change_id)
        else:
            recommendation = 'Investigate as a genuine fault (no correlated change).'
        result.append({
            'id': idx,
            'title': "{} {} RCA".format(vendor, anomaly_metric),
            'status': status,
            'root_cause': r.get('predicted_root_cause'),
            'recommendation': recommendation,
        })
    return result


# ---------------------------------------------------------------------------
# Live readers (boto3 / pg8000 imported lazily inside)
# ---------------------------------------------------------------------------
def _read_live_anomalies():
    """Read anomaly-score jsonl objects from the lab S3 bucket."""
    import boto3

    client = boto3.client(
        's3',
        endpoint_url=os.environ.get('LAB_S3_ENDPOINT', 'http://localhost:4566'),
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1',
    )
    all_records = []
    listing = client.list_objects_v2(Bucket='pm-anomaly-scores')
    for obj in listing.get('Contents', []):
        key = obj['Key']
        body = client.get_object(Bucket='pm-anomaly-scores', Key=key)['Body'].read()
        text = body.decode('utf-8')
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            all_records.append(json.loads(line))
    return map_anomaly_scores(all_records)


def _read_live_rca():
    """Read RCA results from the lab Postgres database via pg8000."""
    import pg8000.dbapi

    conn = pg8000.dbapi.connect(
        host=os.environ.get('LAB_PG_HOST', 'localhost'),
        port=int(os.environ.get('LAB_PG_PORT', '5432')),
        database=os.environ.get('LAB_PG_DB', 'rca'),
        user=os.environ.get('LAB_PG_USER', 'rca'),
        password=os.environ.get('LAB_PG_PASSWORD', 'rca'),
    )
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rca_id, vendor, window_start, anomaly_metric, "
            "correlated_incident_id, correlated_change_id, confidence, "
            "predicted_root_cause FROM rca_results "
            "ORDER BY vendor, window_start, anomaly_metric"
        )
        columns = [
            'rca_id', 'vendor', 'window_start', 'anomaly_metric',
            'correlated_incident_id', 'correlated_change_id', 'confidence',
            'predicted_root_cause',
        ]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()
    return map_rca_rows(rows)


# ---------------------------------------------------------------------------
# Public accessors with fail-safe fallback to demo data
# ---------------------------------------------------------------------------
def get_anomalies():
    """Return anomaly dicts. Live mode falls back to demo data on any error."""
    mode = os.environ.get('LAB_DATA_SOURCE', 'demo')
    if mode != 'live':
        return copy.deepcopy(DEMO_ANOMALIES)
    try:
        result = _read_live_anomalies()
        for item in result:
            if item['id'] in _anomaly_status_overlay:
                item['status'] = _anomaly_status_overlay[item['id']]
        return result
    except Exception as exc:
        log.warning('Live anomaly read failed (%s); falling back to demo data.', exc)
        return copy.deepcopy(DEMO_ANOMALIES)


def get_rca_records():
    """Return RCA record dicts. Live mode falls back to demo data on any error."""
    mode = os.environ.get('LAB_DATA_SOURCE', 'demo')
    if mode != 'live':
        return copy.deepcopy(DEMO_RCA)
    try:
        result = _read_live_rca()
        for item in result:
            if item['id'] in _rca_status_overlay:
                item['status'] = _rca_status_overlay[item['id']]
        return result
    except Exception as exc:
        log.warning('Live RCA read failed (%s); falling back to demo data.', exc)
        return copy.deepcopy(DEMO_RCA)
