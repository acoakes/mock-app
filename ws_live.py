"""Pure diff/emit core for the LIVE-mode ``/ws`` emitter.

This module holds the *pure* logic the LIVE WebSocket loop needs: build a
snapshot of the live-read domains, diff a current read against a previous
snapshot, and decide whether a read looks like the demo-fallback set. It does
NO I/O — no sockets, no ``data_source`` reads — so it is fully unit-testable
without a lab (mirroring how ``data_source`` splits pure mapping functions from
I/O readers).

The LIVE WS loop (see ``ws.py``) stays thin around these functions: read the
four domains through the existing ``data_source`` accessors, hand the reads to
``diff_snapshot``, send the returned envelopes, and keep the returned snapshot.

Envelope shape (unchanged from the DEMO emitter and the frontend contract in
``frontend/src/features/live/liveSocket.ts`` ``tagsForEvent``):

    {"type": "anomaly"|"rca"|"ingestion", "event": "created"|"updated", "id"?: int}

Only the three frontend-supported types are ever emitted:
    anomaly    -> invalidates ['Anomalies','Charts','Dashboard']
    rca        -> invalidates ['RcaList']
    ingestion  -> invalidates ['Ingestion']   (PM files AND tickets map here)

``event`` and ``id`` are advisory (the frontend keys only off ``type``).

Fallback-tolerance (the subtle correctness point)
--------------------------------------------------
The ``data_source`` accessors silently return DEMO data on any live-read
failure. Two hazards follow in LIVE mode:

  (a) a transient live failure returns the small fixed demo set, whose keys
      differ from the live keys — naively this reads as "every demo row is new"
      and would push a storm of fake events; and
  (b) when live recovers, the live keys reappear and would storm again.

``looks_like_demo`` lets the loop detect hazard (a): when a read's natural-key
sets match the ``data_source.DEMO_*`` constants for ALL four domains, the loop
treats it as a transient fallback, SKIPS the diff, and leaves the snapshot
untouched — so nothing is emitted and the live baseline is not corrupted. On
recovery the loop diffs live-against-live, so there is no backlog storm. A
per-poll emit cap in ``diff_snapshot`` is a belt-and-braces guard against any
other unforeseen mass-delta. Deletions never emit (the frontend has no
"removed" event); vanished keys are simply dropped from the new snapshot.
"""

import logging

import data_source

log = logging.getLogger(__name__)

# Belt-and-braces default for the per-poll emit cap (overridable by the caller).
DEFAULT_MAX_EMIT_PER_POLL = 50


# ---------------------------------------------------------------------------
# Natural-key helpers (one per domain). These define what "the same item"
# means across polls — see D4 in the plan.
# ---------------------------------------------------------------------------
def _anomaly_key(a):
    """Stable identity for an anomaly.

    ``map_anomaly_scores`` assigns the UI ``id`` by POSITION after sorting, so
    ``id`` renumbers as new anomalies land and is NOT a stable key. ``timestamp``
    (= ``window_start``) plus ``description`` (which encodes
    ``vendor/site (region): metric z=.. at window``) together are stable.
    """
    return (a.get('timestamp'), a.get('description'))


def _rca_key(r):
    """Stable identity for an RCA record.

    Prefer the lab ``rca_id`` (``vendor|region|site|window|metric``), which the
    live path carries via ``include_rca_id=True``. Demo records have no
    ``rca_id``, so fall back to ``(title, status)`` for them.
    """
    rca_id = r.get('rca_id')
    if rca_id:
        return ('rca_id', rca_id)
    return ('title', r.get('title'), r.get('status'))


# ---------------------------------------------------------------------------
# Snapshot construction (pure)
# ---------------------------------------------------------------------------
def build_snapshot(anomalies, rca, pm_files, tickets):
    """Build a snapshot from the four live-read domains.

    Returns a dict of natural-key collections:
        {
          "anomaly":       set[(timestamp, description)],
          "rca":           set[key],              # see _rca_key
          "ingestion_pm":  dict[str, str],        # {s3 object key: stage}
          "ticket":        set[str],              # {ticket_id}
        }
    Pure: builds only from the passed-in lists, no I/O.
    """
    return {
        'anomaly': {_anomaly_key(a) for a in anomalies},
        'rca': {_rca_key(r) for r in rca},
        # PM files keep stage so an ``ingested`` -> ``parsed`` transition on an
        # already-seen key can emit one ``updated`` envelope.
        'ingestion_pm': {f.get('key'): f.get('stage') for f in pm_files if f.get('key')},
        'ticket': {t.get('ticket_id') for t in tickets if t.get('ticket_id')},
    }


# ---------------------------------------------------------------------------
# Demo-fallback detection (pure) — the D5.2 gate
# ---------------------------------------------------------------------------
def looks_like_demo(current_reads):
    """True when ``current_reads`` matches the demo-fallback set for ALL domains.

    Compares the current read's natural-key sets against the public
    ``data_source.DEMO_*`` constants (read-only; this does NOT edit
    ``data_source``). Used by the LIVE loop to detect a transient live-read
    failure (the accessors fail-safe to demo data) and skip the diff rather than
    emit a storm of fake "new" events.

    All four domains must match the demo sets simultaneously; real lab data is
    extremely unlikely to coincide with the exact demo keys across every domain,
    so this is a safe, conservative gate.
    """
    demo = build_snapshot(
        data_source.DEMO_ANOMALIES,
        data_source.DEMO_RCA,
        data_source.DEMO_PM_FILES,
        data_source.DEMO_TICKETS,
    )
    current = build_snapshot(
        current_reads.get('anomalies', []),
        current_reads.get('rca', []),
        current_reads.get('pm_files', []),
        current_reads.get('tickets', []),
    )
    return (
        current['anomaly'] == demo['anomaly']
        and current['rca'] == demo['rca']
        and set(current['ingestion_pm']) == set(demo['ingestion_pm'])
        and current['ticket'] == demo['ticket']
    )


# ---------------------------------------------------------------------------
# The diff/emit core (pure) — given prev + current reads, produce envelopes
# and the new snapshot.
# ---------------------------------------------------------------------------
def diff_snapshot(prev, current_reads, max_emit=DEFAULT_MAX_EMIT_PER_POLL):
    """Diff ``current_reads`` against ``prev`` snapshot; return (envelopes, new_snapshot).

    ``current_reads`` is ``{"anomalies":[...], "rca":[...], "pm_files":[...],
    "tickets":[...]}`` (the shape produced from the four ``data_source``
    accessors).

    Behaviour:
      * ``prev is None`` -> SEED silently: return ``([], current_snapshot)``. The
        first poll after connect establishes the baseline and emits NOTHING (we
        announce only CHANGES observed while connected, never the backlog).
      * otherwise -> emit one envelope per genuinely-new item:
          - new anomaly key   -> {"type":"anomaly","event":"created","id":<ui id>}
          - new rca key       -> {"type":"rca","event":"created","id":<ui id>}
          - new PM-file key    -> {"type":"ingestion","event":"created"}
          - PM stage ``ingested`` -> ``parsed`` on a seen key
                              -> {"type":"ingestion","event":"updated"}
          - new ticket_id     -> {"type":"ingestion","event":"created"}
        ``id`` is advisory; it is omitted for ingestion (as the DEMO sequence
        does and the frontend ignores it there).

    Deletions never emit: keys that vanish are just dropped from the new
    snapshot (the frontend has no "removed" event).

    The number of envelopes is capped at ``max_emit`` (belt-and-braces guard
    against an unforeseen mass-delta). Excess new keys are STILL folded into the
    returned snapshot, so they are not re-emitted on the next poll; a WARNING is
    logged when the cap trips.

    Pure: no I/O. The LIVE loop supplies ``current_reads`` and persists the
    returned snapshot.
    """
    anomalies = current_reads.get('anomalies', [])
    rca = current_reads.get('rca', [])
    pm_files = current_reads.get('pm_files', [])
    tickets = current_reads.get('tickets', [])

    new_snapshot = build_snapshot(anomalies, rca, pm_files, tickets)

    # First poll seeds the baseline silently (D5.1).
    if prev is None:
        return [], new_snapshot

    prev_anomaly = prev.get('anomaly', set())
    prev_rca = prev.get('rca', set())
    prev_pm = prev.get('ingestion_pm', {})
    prev_ticket = prev.get('ticket', set())

    envelopes = []

    # New anomalies: emit created with the current UI id (advisory).
    for a in anomalies:
        if _anomaly_key(a) not in prev_anomaly:
            envelopes.append({'type': 'anomaly', 'event': 'created', 'id': a.get('id')})

    # New RCA records: emit created with the current UI id (advisory).
    for r in rca:
        if _rca_key(r) not in prev_rca:
            envelopes.append({'type': 'rca', 'event': 'created', 'id': r.get('id')})

    # PM files: a brand-new key is ``created``; an ``ingested`` -> ``parsed``
    # transition on a previously-seen key is ``updated`` (parsed records landed).
    for f in pm_files:
        key = f.get('key')
        if not key:
            continue
        stage = f.get('stage')
        if key not in prev_pm:
            envelopes.append({'type': 'ingestion', 'event': 'created'})
        elif prev_pm[key] == 'ingested' and stage == 'parsed':
            envelopes.append({'type': 'ingestion', 'event': 'updated'})

    # New tickets: emit created (no id — ingestion ignores it on the frontend).
    for t in tickets:
        tid = t.get('ticket_id')
        if tid and tid not in prev_ticket:
            envelopes.append({'type': 'ingestion', 'event': 'created'})

    # Per-poll emit cap (D5.3). The snapshot already reflects ALL current keys,
    # so capped-away items will NOT be re-emitted next poll.
    if len(envelopes) > max_emit:
        log.warning(
            'ws_live diff produced %d envelopes; capping to %d for this poll.',
            len(envelopes), max_emit,
        )
        envelopes = envelopes[:max_emit]

    return envelopes, new_snapshot
