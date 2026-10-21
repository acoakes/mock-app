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

DEMO_PM_FILES = [
    {'key': 'vendor_a/vendora_pm.csv', 'vendor': 'vendor_a', 'size': 1838, 'stage': 'parsed', 'records': 26},
    {'key': 'vendor_b/vendorb_pm.json', 'vendor': 'vendor_b', 'size': 4024, 'stage': 'parsed', 'records': 26},
    {'key': 'vendor_c/vendorc_pm.json', 'vendor': 'vendor_c', 'size': 3745, 'stage': 'ingested', 'records': None},
]

DEMO_TICKETS = [
    {'ticket_id': 'INC-00001', 'ticket_type': 'incident', 'vendor': 'vendor_a', 'window_start': '2024-01-15T14:40:00Z', 'summary': 'Latency spike at site-0207'},
    {'ticket_id': 'CHG-00003', 'ticket_type': 'change', 'vendor': 'vendor_b', 'window_start': '2024-01-15T14:20:00Z', 'summary': 'Config rollout at site-0411'},
]


# ---------------------------------------------------------------------------
# Per-process demo stores (mutated in place by demo-mode POST routes) and
# status overlays for live-mode mutations (int-keyed)
# ---------------------------------------------------------------------------
_demo_anomalies = copy.deepcopy(DEMO_ANOMALIES)
_demo_rca = copy.deepcopy(DEMO_RCA)

_anomaly_status_overlay = {}
_rca_status_overlay = {}


def _is_live():
    return os.environ.get('LAB_DATA_SOURCE', 'demo') == 'live'


def set_anomaly_status(id, status):
    """Set the status for the anomaly with the given id.

    In live mode the override is recorded in the overlay applied on read; in
    demo mode the persistent demo store is mutated in place.
    """
    if _is_live():
        _anomaly_status_overlay[int(id)] = status
    else:
        for anomaly in _demo_anomalies:
            if anomaly['id'] == int(id):
                anomaly['status'] = status
                break


def set_rca_status(id, status):
    """Set the status for the RCA record with the given id.

    In live mode the override is recorded in the overlay applied on read; in
    demo mode the persistent demo store is mutated in place.
    """
    if _is_live():
        _rca_status_overlay[int(id)] = status
    else:
        for rca in _demo_rca:
            if rca['id'] == int(id):
                rca['status'] = status
                break


# ---------------------------------------------------------------------------
# Pure mapping functions (no I/O)
# ---------------------------------------------------------------------------
def map_anomaly_scores(records):
    """Map raw lab anomaly-score records to UI anomaly dicts.

    Keeps only records where is_anomaly is true, sorts by (vendor, region,
    site, window_start), assigns 1-based ids by position and synthesises the UI
    fields. Severity is derived from abs(score).
    """
    kept = [r for r in records if r.get('is_anomaly')]
    kept = sorted(
        kept,
        key=lambda r: (r.get('vendor'), r.get('region'), r.get('site'), r.get('window_start')),
    )
    result = []
    for idx, r in enumerate(kept, start=1):
        vendor = r.get('vendor')
        region = r.get('region')
        site = r.get('site')
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
            'description': "{}/{} ({}): {} anomaly (z={:.2f}) at {}".format(vendor, site, region, metric, score, window_start),
            'severity': severity,
            'status': 'open',
            'timestamp': window_start,
        })
    return result


def map_rca_rows(rows, include_rca_id=False):
    """Map raw lab rca_results rows (as dicts) to UI RCA record dicts.

    Orders by (vendor, region, site, window_start, anomaly_metric), assigns
    1-based ids by position and synthesises the UI fields.

    By default the result keeps EXACTLY the demo key set
    ``{id, title, status, root_cause, recommendation}`` so demo output and the
    existing ``test_map_rca_rows_keys_unchanged`` stay green. Live callers pass
    ``include_rca_id=True`` to also carry the lab ``rca_id`` (used to resolve the
    UI id back to the lab id for the subgraph fetch).
    """
    ordered = sorted(
        rows,
        key=lambda r: (
            r.get('vendor'), r.get('region'), r.get('site'),
            r.get('window_start'), r.get('anomaly_metric'),
        ),
    )
    result = []
    for idx, r in enumerate(ordered, start=1):
        vendor = r.get('vendor')
        site = r.get('site')
        anomaly_metric = r.get('anomaly_metric')
        window_start = r.get('window_start')
        confidence = r.get('confidence')
        correlated_change_id = r.get('correlated_change_id')
        status = 'in_progress' if confidence is not None and confidence >= 0.8 else 'open'
        if correlated_change_id:
            recommendation = "Review and consider rolling back change {}".format(correlated_change_id)
        else:
            recommendation = 'Investigate as a genuine fault (no correlated change).'
        item = {
            'id': idx,
            'title': "{}/{} {} @ {}".format(vendor, site, anomaly_metric, window_start),
            'status': status,
            'root_cause': r.get('predicted_root_cause'),
            'recommendation': recommendation,
        }
        if include_rca_id:
            item['rca_id'] = r.get('rca_id')
        result.append(item)
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
            "SELECT rca_id, vendor, region, site, window_start, anomaly_metric, "
            "correlated_incident_id, correlated_change_id, confidence, "
            "predicted_root_cause FROM rca_results "
            "ORDER BY vendor, region, site, window_start, anomaly_metric"
        )
        columns = [
            'rca_id', 'vendor', 'region', 'site', 'window_start', 'anomaly_metric',
            'correlated_incident_id', 'correlated_change_id', 'confidence',
            'predicted_root_cause',
        ]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()
    return map_rca_rows(rows, include_rca_id=True)


# ---------------------------------------------------------------------------
# Public accessors with fail-safe fallback to demo data
# ---------------------------------------------------------------------------
def get_anomalies():
    """Return anomaly dicts. Live mode falls back to demo data on any error."""
    if not _is_live():
        return copy.deepcopy(_demo_anomalies)
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
    if not _is_live():
        return copy.deepcopy(_demo_rca)
    try:
        result = _read_live_rca()
        for item in result:
            if item['id'] in _rca_status_overlay:
                item['status'] = _rca_status_overlay[item['id']]
        return result
    except Exception as exc:
        log.warning('Live RCA read failed (%s); falling back to demo data.', exc)
        return copy.deepcopy(DEMO_RCA)


# ---------------------------------------------------------------------------
# Live-mode RCA subgraph (gremlinpython imported lazily, fail-safe to None)
# ---------------------------------------------------------------------------
def _resolve_rca_id(ui_id):
    """Map a UI /rca/<id> to the lab rca_id by scanning the live RCA records.

    Returns the matching record's ``rca_id`` or None if there is no match (or the
    matched record carries no rca_id). Demo records never carry rca_id, so this
    naturally returns None outside live mode.
    """
    for record in get_rca_records():
        if record.get('id') == int(ui_id):
            return record.get('rca_id')
    return None


def get_rca_subgraph(ui_id):
    """Return the {nodes, edges} RCA subgraph for a UI id, or None.

    Live mode only: returns None in demo mode. In live mode it resolves the UI id
    to the lab rca_id (None => return None) and lazy-imports rca_graph_client to
    fetch the subgraph. On ANY exception (Gremlin down, bad data, ...) it logs a
    warning and returns None so the route can fail safe to a placeholder and never
    500 (FR-13).
    """
    if not _is_live():
        return None
    try:
        rca_id = _resolve_rca_id(ui_id)
        if rca_id is None:
            return None
        import rca_graph_client
        return rca_graph_client.get_rca_chain(rca_id)
    except Exception as exc:
        log.warning('Live RCA subgraph fetch failed (%s); rendering placeholder.', exc)
        return None


# ---------------------------------------------------------------------------
# Live-mode ingestion feed: PM files (S3) + tickets (DynamoDB)
# ---------------------------------------------------------------------------
def _read_live_pm_files():
    """List PM files in S3, deriving a processing stage per file.

    A file is 'ingested' once it lands in pm-raw; it becomes 'parsed' once a
    matching normalized object exists under pm-aggregated/normalized/ (with the
    CSV/JSON extension swapped to .json, as CDF writes). Newest first.
    """
    import boto3

    client = boto3.client(
        's3',
        endpoint_url=os.environ.get('LAB_S3_ENDPOINT', 'http://localhost:4566'),
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1',
    )

    # Collect normalized keys (CDF output) for stage derivation + record counts.
    normalized = {}
    norm_listing = client.list_objects_v2(Bucket='pm-aggregated', Prefix='normalized/')
    for obj in norm_listing.get('Contents', []):
        # normalized/<vendor>/<file>.json  -> keyed by "<vendor>/<file>.json"
        rel = obj['Key'][len('normalized/'):]
        normalized[rel] = obj

    files = []
    raw_listing = client.list_objects_v2(Bucket='pm-raw')
    for obj in raw_listing.get('Contents', []):
        key = obj['Key']  # "<vendor>/<file>.<ext>"
        vendor = key.split('/', 1)[0] if '/' in key else ''
        # CDF writes normalized output as .json regardless of source extension.
        base = key.rsplit('.', 1)[0]
        norm_key = base + '.json'
        parsed_obj = normalized.get(norm_key)
        records = None
        if parsed_obj is not None:
            # Derive record count from the normalized object. CDF may write either a
            # JSON array or line-delimited JSON, so handle both.
            try:
                body = client.get_object(Bucket='pm-aggregated', Key='normalized/' + norm_key)['Body'].read()
                text = body.decode('utf-8').strip()
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    records = len(parsed)
                else:
                    records = 1
            except json.JSONDecodeError:
                # Fall back to counting non-empty lines (line-delimited JSON).
                records = sum(1 for ln in text.splitlines() if ln.strip())
            except Exception:
                records = None
        files.append({
            'key': key,
            'vendor': vendor,
            'size': obj.get('Size', 0),
            'stage': 'parsed' if parsed_obj is not None else 'ingested',
            'records': records,
            'last_modified': obj.get('LastModified'),
        })

    files.sort(key=lambda f: (f.get('last_modified') is not None, f.get('last_modified')), reverse=True)
    # Strip the datetime before returning (not JSON-serialisable / not needed in UI).
    for f in files:
        f.pop('last_modified', None)
    return files


def _read_live_tickets():
    """Scan the accumulating ticketing-feed DynamoDB table. Newest first."""
    import boto3

    client = boto3.client(
        'dynamodb',
        endpoint_url=os.environ.get('LAB_S3_ENDPOINT', 'http://localhost:4566'),
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1',
    )

    tickets = []
    paginator = client.get_paginator('scan')
    for page in paginator.paginate(TableName='ticketing-feed'):
        for item in page.get('Items', []):
            def _s(name):
                cell = item.get(name, {})
                return cell.get('S') or cell.get('N') or ''
            tickets.append({
                'ticket_id': _s('ticket_id') or _s('sk'),
                'ticket_type': _s('ticket_type') or _s('type'),
                'vendor': _s('vendor') or _s('pk'),
                'window_start': _s('window_start'),
                'summary': _s('summary') or _s('description'),
            })

    tickets.sort(key=lambda t: t.get('window_start') or '', reverse=True)
    return tickets


def get_pm_ingestion():
    """Return PM-file ingestion rows. Live mode falls back to demo data on error."""
    if not _is_live():
        return copy.deepcopy(DEMO_PM_FILES)
    try:
        return _read_live_pm_files()
    except Exception as exc:
        log.warning('Live PM-file read failed (%s); falling back to demo data.', exc)
        return copy.deepcopy(DEMO_PM_FILES)


def get_ticket_feed():
    """Return ticket-feed rows. Live mode falls back to demo data on error."""
    if not _is_live():
        return copy.deepcopy(DEMO_TICKETS)
    try:
        return _read_live_tickets()
    except Exception as exc:
        log.warning('Live ticket read failed (%s); falling back to demo data.', exc)
        return copy.deepcopy(DEMO_TICKETS)
