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

# Static demo chart data (byte-identical for the BDD tests, which run in demo mode).
DEMO_CHARTS = {
    'by_vendor': {'labels': ['vendor_a', 'vendor_b', 'vendor_c'], 'values': [3, 1, 1]},
    'by_severity': {'labels': ['HIGH', 'MEDIUM', 'LOW'], 'values': [2, 2, 1]},
    'over_time': {
        'labels': ['2024-01-15T12:00:00Z', '2024-01-15T13:00:00Z', '2024-01-15T14:00:00Z'],
        'values': [1, 2, 2],
    },
}

# Static demo KPIs (byte-identical for the BDD tests, which run in demo mode).
DEMO_KPIS = [
    {'name': 'Throughput', 'value': '94.2', 'unit': '%'},
    {'name': 'Data Quality Score', 'value': '87.5', 'unit': '%'},
    {'name': 'Anomaly Rate', 'value': '3.1', 'unit': '%'},
    {'name': 'Processing Latency', 'value': '142', 'unit': 'ms'},
    {'name': 'Records Processed', 'value': '1,284,302', 'unit': ''},
]


# ---------------------------------------------------------------------------
# Per-process demo stores (mutated in place by demo-mode POST routes) and
# status overlays for live-mode mutations (int-keyed)
# ---------------------------------------------------------------------------
_demo_anomalies = copy.deepcopy(DEMO_ANOMALIES)
_demo_rca = copy.deepcopy(DEMO_RCA)

_anomaly_status_overlay = {}
_rca_status_overlay = {}


def reset_demo_state():
    """Restore the demo stores and live-mode status overlays to their defaults.

    Used only for test isolation (a demo-mode /__reset endpoint calls this): the
    demo POST routes mutate _demo_anomalies / _demo_rca in place, so without a
    reset those mutations persist across scenarios and break non-idempotent
    tests (e.g. a scenario that needs an 'in_progress' RCA record after a prior
    scenario resolved it).
    """
    global _demo_anomalies, _demo_rca
    _demo_anomalies = copy.deepcopy(DEMO_ANOMALIES)
    _demo_rca = copy.deepcopy(DEMO_RCA)
    _anomaly_status_overlay.clear()
    _rca_status_overlay.clear()


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
def _s3_client():
    import boto3

    return boto3.client(
        's3',
        endpoint_url=os.environ.get('LAB_S3_ENDPOINT', 'http://localhost:4566'),
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1',
    )


def _read_live_score_records():
    """Read ALL raw anomaly-score records (anomalous and not) from S3."""
    client = _s3_client()
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
    return all_records


def _mean_throughput_mbps():
    """Mean of the throughput_mbps metric across the aggregated events (agg/ prefix).

    Reads the CDF aggregate output under s3://pm-aggregated/agg/ and averages the
    per-event 'mean' for the throughput_mbps metric. Returns None if no such events
    exist (so the caller can fall back to a placeholder).
    """
    client = _s3_client()
    means = []
    paginator = client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket='pm-aggregated', Prefix='agg/'):
        for obj in page.get('Contents', []):
            key = obj['Key']
            # agg/<vendor>/<region>/<site>/<metric>/<window>.json
            if '/throughput_mbps/' not in key:
                continue
            body = client.get_object(Bucket='pm-aggregated', Key=key)['Body'].read()
            event = json.loads(body.decode('utf-8'))
            if event.get('mean') is not None:
                means.append(float(event['mean']))
    if not means:
        return None
    return sum(means) / len(means)


def _count_raw_rows(client, key):
    """Count data rows in a raw PM file: CSV lines minus header, or JSON array length."""
    body = client.get_object(Bucket='pm-raw', Key=key)['Body'].read()
    text = body.decode('utf-8').strip()
    if not text:
        return 0
    if key.lower().endswith('.json'):
        try:
            parsed = json.loads(text)
            return len(parsed) if isinstance(parsed, list) else 1
        except json.JSONDecodeError:
            return sum(1 for ln in text.splitlines() if ln.strip())
    # CSV: non-empty lines minus the header row.
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return max(0, len(lines) - 1)


def _data_quality_score(pm_files):
    """DQS = parsed records / submitted raw rows, as a percentage.

    'parsed' is the normalized record count already derived per file; 'submitted'
    is the raw row count read from pm-raw. Returns None if nothing has been
    submitted yet (caller falls back to a placeholder).
    """
    client = _s3_client()
    submitted = 0
    parsed = 0
    for f in pm_files:
        parsed += f.get('records') or 0
        submitted += _count_raw_rows(client, f['key'])
    if submitted <= 0:
        return None
    # Parsed can never exceed submitted; clamp defensively against count skew.
    return 100.0 * min(parsed, submitted) / submitted


def _read_live_anomalies():
    """Read anomaly-score jsonl objects from the lab S3 bucket."""
    return map_anomaly_scores(_read_live_score_records())


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


# ---------------------------------------------------------------------------
# Date-range filtering (shared by KPIs and charts)
# ---------------------------------------------------------------------------
def _in_date_range(ts, date_from, date_to):
    """True if the ISO timestamp's date (first 10 chars) is within [from, to].

    Either bound may be empty/None (open-ended). Comparison is lexicographic on
    the YYYY-MM-DD prefix, which is correct for ISO-8601 dates.
    """
    if not ts:
        return not (date_from or date_to)
    day = ts[:10]
    if date_from and day < date_from:
        return False
    if date_to and day > date_to:
        return False
    return True


def _filter_anomalies_by_date(anomalies, date_from, date_to):
    if not date_from and not date_to:
        return anomalies
    return [a for a in anomalies if _in_date_range(a.get('timestamp', ''), date_from, date_to)]


# ---------------------------------------------------------------------------
# Live-mode dashboard KPIs (derived from real lab data, demo fallback)
# ---------------------------------------------------------------------------
def get_dashboard_kpis(date_from='', date_to=''):
    """Return the dashboard KPI list.

    Demo mode returns the static DEMO_KPIS (kept byte-identical for the BDD
    tests). Live mode derives real metrics from the lab, optionally filtered to
    the [date_from, date_to] range (YYYY-MM-DD, either open-ended):
      * Records Processed = total normalized PM records across all files
      * Anomaly Rate      = anomalies / total scored records, as a percentage
    Throughput and Data Quality Score are derived from live data; Processing
    Latency has no real source so it stays a placeholder. Any failure falls
    back to DEMO_KPIS.
    """
    if not _is_live():
        return copy.deepcopy(DEMO_KPIS)
    try:
        score_records = _read_live_score_records()
        if date_from or date_to:
            score_records = [
                r for r in score_records
                if _in_date_range(r.get('window_start', ''), date_from, date_to)
            ]
        total_scored = len(score_records)
        anomaly_count = sum(1 for r in score_records if r.get('is_anomaly'))
        pm_files = _read_live_pm_files()
        records_processed = sum(f['records'] for f in pm_files if f.get('records'))

        if total_scored > 0:
            anomaly_rate = '{:.1f}'.format(100.0 * anomaly_count / total_scored)
        else:
            anomaly_rate = '0.0'

        # Throughput: mean of the real throughput_mbps metric across aggregates.
        mean_tput = _mean_throughput_mbps()
        throughput = ('{:.1f}'.format(mean_tput), 'mbps') if mean_tput is not None else ('94.2', '%')

        # Data Quality Score: parsed / submitted raw rows.
        dqs = _data_quality_score(pm_files)
        dqs_value = '{:.1f}'.format(dqs) if dqs is not None else '87.5'

        # Same five KPI names as demo mode (keeps the "exactly 5" contract), but
        # Throughput / Data Quality Score / Anomaly Rate / Records Processed are
        # derived from live lab data. Processing Latency has no lab source, so it
        # stays a stable placeholder in both modes.
        return [
            {'name': 'Throughput', 'value': throughput[0], 'unit': throughput[1]},
            {'name': 'Data Quality Score', 'value': dqs_value, 'unit': '%'},
            {'name': 'Anomaly Rate', 'value': anomaly_rate, 'unit': '%'},
            {'name': 'Processing Latency', 'value': '142', 'unit': 'ms'},
            {'name': 'Records Processed', 'value': '{:,}'.format(records_processed), 'unit': ''},
        ]
    except Exception as exc:
        log.warning('Live KPI build failed (%s); falling back to demo KPIs.', exc)
        return copy.deepcopy(DEMO_KPIS)


# ---------------------------------------------------------------------------
# Live-mode dashboard charts (anomalies by vendor / severity / over time)
# ---------------------------------------------------------------------------
def get_anomaly_charts(date_from='', date_to=''):
    """Return chart datasets for the dashboard.

    Demo mode returns the static DEMO_CHARTS (byte-identical for the BDD tests).
    Live mode derives three datasets from the live anomaly list, optionally
    filtered to the [date_from, date_to] range (YYYY-MM-DD, either open-ended):
      * by_vendor   - anomaly count per vendor (bar)
      * by_severity - anomaly count per HIGH/MEDIUM/LOW (doughnut)
      * over_time   - anomaly count per window_start, chronological (line)
    Each dataset is {'labels': [...], 'values': [...]}. Any failure falls back
    to DEMO_CHARTS.
    """
    if not _is_live():
        return copy.deepcopy(DEMO_CHARTS)
    try:
        anomalies = _filter_anomalies_by_date(get_anomalies(), date_from, date_to)

        # by_vendor — the live anomaly 'description' starts "<vendor>/<site> ...",
        # so derive the vendor from the leading token before the first '/'.
        vendor_counts = {}
        for a in anomalies:
            desc = a.get('description', '')
            vendor = desc.split('/', 1)[0].strip() if '/' in desc else 'unknown'
            vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
        vendors = sorted(vendor_counts)
        by_vendor = {'labels': vendors, 'values': [vendor_counts[v] for v in vendors]}

        # by_severity — fixed HIGH/MEDIUM/LOW ordering.
        sev_order = ['HIGH', 'MEDIUM', 'LOW']
        sev_counts = {s: 0 for s in sev_order}
        for a in anomalies:
            sev = a.get('severity')
            if sev in sev_counts:
                sev_counts[sev] += 1
        by_severity = {'labels': sev_order, 'values': [sev_counts[s] for s in sev_order]}

        # over_time — count anomalies per window_start (timestamp), chronological.
        time_counts = {}
        for a in anomalies:
            ts = a.get('timestamp', '')
            time_counts[ts] = time_counts.get(ts, 0) + 1
        times = sorted(t for t in time_counts if t)
        over_time = {'labels': times, 'values': [time_counts[t] for t in times]}

        return {
            'by_vendor': by_vendor,
            'by_severity': by_severity,
            'over_time': over_time,
        }
    except Exception as exc:
        log.warning('Live chart build failed (%s); falling back to demo charts.', exc)
        return copy.deepcopy(DEMO_CHARTS)
