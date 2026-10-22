"""Pure unit tests for the LIVE-mode diff/emit core (ws_live.py).

These tests use hand-built dict fixtures only; they never touch a socket, S3,
Postgres, or DynamoDB. They prove the pure logic the thin WS loop relies on:
the right envelopes for new data, NOTHING when unchanged, and NO storm on the
demo fallback / transient-failure path. Style mirrors
``tests/test_data_source_mapping.py``.
"""

import data_source
import ws_live


# ---------------------------------------------------------------------------
# Live-shaped fixtures (NOT the demo set, so looks_like_demo is False for them)
# ---------------------------------------------------------------------------
def _anomaly(ts, desc, id=1):
    return {'id': id, 'description': desc, 'severity': 'HIGH', 'status': 'open', 'timestamp': ts}


def _rca(rca_id, title='t', status='open', id=1):
    return {'id': id, 'title': title, 'status': status, 'root_cause': 'rc',
            'recommendation': 'fix', 'rca_id': rca_id}


def _pm(key, stage='ingested', vendor='v'):
    return {'key': key, 'vendor': vendor, 'size': 10, 'stage': stage, 'records': None}


def _ticket(ticket_id):
    return {'ticket_id': ticket_id, 'ticket_type': 'incident', 'vendor': 'v',
            'window_start': '2024-02-01T00:00:00Z', 'summary': 's'}


def _reads(anomalies=None, rca=None, pm_files=None, tickets=None):
    return {
        'anomalies': anomalies or [],
        'rca': rca or [],
        'pm_files': pm_files or [],
        'tickets': tickets or [],
    }


# A baseline live read distinct from every demo domain.
def _live_reads():
    return _reads(
        anomalies=[_anomaly('2024-02-01T00:00', 'acme/site-1 (eu): latency anomaly (z=3.10) at 2024-02-01T00:00')],
        rca=[_rca('acme|eu|site-1|2024-02-01T00:00|latency')],
        pm_files=[_pm('acme/acme_pm.csv', stage='ingested')],
        tickets=[_ticket('INC-10001')],
    )


# ---------------------------------------------------------------------------
# (a) first poll seeds and emits nothing
# ---------------------------------------------------------------------------
def test_diff_snapshot_seeds_silently_on_first_poll():
    envelopes, snapshot = ws_live.diff_snapshot(None, _live_reads(), max_emit=50)
    assert envelopes == []
    # Baseline captured so subsequent identical polls are no-ops.
    assert snapshot['anomaly']
    assert snapshot['rca']
    assert snapshot['ingestion_pm']
    assert snapshot['ticket']


def test_diff_snapshot_no_emit_when_unchanged():
    reads = _live_reads()
    _, snapshot = ws_live.diff_snapshot(None, reads, max_emit=50)
    envelopes, snapshot2 = ws_live.diff_snapshot(snapshot, reads, max_emit=50)
    assert envelopes == []
    assert snapshot2 == snapshot


# ---------------------------------------------------------------------------
# (b) a new anomaly -> one created envelope, not re-emitted next poll
# ---------------------------------------------------------------------------
def test_new_anomaly_emits_created_once():
    base = _live_reads()
    _, snap = ws_live.diff_snapshot(None, base, max_emit=50)

    grew = _reads(
        anomalies=base['anomalies'] + [
            _anomaly('2024-02-01T01:00', 'acme/site-2 (eu): latency anomaly (z=4.00) at 2024-02-01T01:00', id=2),
        ],
        rca=base['rca'], pm_files=base['pm_files'], tickets=base['tickets'],
    )
    envelopes, snap2 = ws_live.diff_snapshot(snap, grew, max_emit=50)
    assert envelopes == [{'type': 'anomaly', 'event': 'created', 'id': 2}]

    # Same read again -> nothing new.
    envelopes2, _ = ws_live.diff_snapshot(snap2, grew, max_emit=50)
    assert envelopes2 == []


# ---------------------------------------------------------------------------
# (c) rca identity uses rca_id, not the positional id
# ---------------------------------------------------------------------------
def test_new_rca_emits_created():
    base = _live_reads()
    _, snap = ws_live.diff_snapshot(None, base, max_emit=50)
    grew = _reads(
        anomalies=base['anomalies'],
        rca=base['rca'] + [_rca('acme|eu|site-9|2024-02-01T02:00|throughput', id=2)],
        pm_files=base['pm_files'], tickets=base['tickets'],
    )
    envelopes, _ = ws_live.diff_snapshot(snap, grew, max_emit=50)
    assert envelopes == [{'type': 'rca', 'event': 'created', 'id': 2}]


def test_rca_identity_is_rca_id_not_position():
    # Same rca_ids, reordered (positional id swaps) -> no emits.
    r1 = _rca('acme|eu|s1|w1|m1', id=1)
    r2 = _rca('acme|eu|s2|w2|m2', id=2)
    base = _reads(rca=[r1, r2])
    _, snap = ws_live.diff_snapshot(None, base, max_emit=50)

    reordered = _reads(rca=[
        dict(r2, id=1),  # same rca_id, new positional id
        dict(r1, id=2),
    ])
    envelopes, _ = ws_live.diff_snapshot(snap, reordered, max_emit=50)
    assert envelopes == []


# ---------------------------------------------------------------------------
# (d) ingestion: new PM file -> created; ingested->parsed -> updated
# ---------------------------------------------------------------------------
def test_new_pm_file_emits_ingestion_created():
    base = _live_reads()
    _, snap = ws_live.diff_snapshot(None, base, max_emit=50)
    grew = _reads(
        anomalies=base['anomalies'], rca=base['rca'],
        pm_files=base['pm_files'] + [_pm('bravo/bravo_pm.json', stage='ingested')],
        tickets=base['tickets'],
    )
    envelopes, _ = ws_live.diff_snapshot(snap, grew, max_emit=50)
    assert envelopes == [{'type': 'ingestion', 'event': 'created'}]


def test_pm_stage_transition_emits_ingestion_updated():
    base = _live_reads()  # single pm file at stage 'ingested'
    _, snap = ws_live.diff_snapshot(None, base, max_emit=50)
    parsed = _reads(
        anomalies=base['anomalies'], rca=base['rca'],
        pm_files=[_pm('acme/acme_pm.csv', stage='parsed')],
        tickets=base['tickets'],
    )
    envelopes, snap2 = ws_live.diff_snapshot(snap, parsed, max_emit=50)
    assert envelopes == [{'type': 'ingestion', 'event': 'updated'}]
    # Not re-emitted once the new stage is the baseline.
    envelopes2, _ = ws_live.diff_snapshot(snap2, parsed, max_emit=50)
    assert envelopes2 == []


# ---------------------------------------------------------------------------
# (e) new ticket -> ingestion created
# ---------------------------------------------------------------------------
def test_new_ticket_emits_ingestion_created():
    base = _live_reads()
    _, snap = ws_live.diff_snapshot(None, base, max_emit=50)
    grew = _reads(
        anomalies=base['anomalies'], rca=base['rca'], pm_files=base['pm_files'],
        tickets=base['tickets'] + [_ticket('CHG-20002')],
    )
    envelopes, _ = ws_live.diff_snapshot(snap, grew, max_emit=50)
    assert envelopes == [{'type': 'ingestion', 'event': 'created'}]


# ---------------------------------------------------------------------------
# (f) emit cap limits envelopes while still advancing the snapshot
# ---------------------------------------------------------------------------
def test_emit_cap_limits_and_still_advances_snapshot():
    base = _reads()
    _, snap = ws_live.diff_snapshot(None, base, max_emit=2)  # seed empty baseline
    many = _reads(anomalies=[
        _anomaly('2024-03-01T0%d:00' % i, 'desc-%d' % i, id=i) for i in range(5)
    ])
    envelopes, snap2 = ws_live.diff_snapshot(snap, many, max_emit=2)
    assert len(envelopes) == 2
    # All five keys are folded into the snapshot, so capped items are NOT
    # re-emitted on the next identical poll.
    envelopes2, _ = ws_live.diff_snapshot(snap2, many, max_emit=2)
    assert envelopes2 == []
    assert len(snap2['anomaly']) == 5


# ---------------------------------------------------------------------------
# (g) looks_like_demo: True for the DEMO_* sets, False for a live read
# ---------------------------------------------------------------------------
def test_looks_like_demo_true_for_demo_constants():
    demo_reads = _reads(
        anomalies=data_source.DEMO_ANOMALIES,
        rca=data_source.DEMO_RCA,
        pm_files=data_source.DEMO_PM_FILES,
        tickets=data_source.DEMO_TICKETS,
    )
    assert ws_live.looks_like_demo(demo_reads) is True


def test_looks_like_demo_false_for_live_read():
    assert ws_live.looks_like_demo(_live_reads()) is False


# ---------------------------------------------------------------------------
# (h) deletions emit nothing and drop from the snapshot
# ---------------------------------------------------------------------------
def test_deletions_emit_nothing_and_drop_from_snapshot():
    base = _live_reads()
    _, snap = ws_live.diff_snapshot(None, base, max_emit=50)
    # Everything removed (e.g. lab retention pruning).
    shrunk = _reads()
    envelopes, snap2 = ws_live.diff_snapshot(snap, shrunk, max_emit=50)
    assert envelopes == []
    assert snap2['anomaly'] == set()
    assert snap2['rca'] == set()
    assert snap2['ingestion_pm'] == {}
    assert snap2['ticket'] == set()
