"""WebSocket live-push channel (design §3 / §9 step 5, the [LATER] slice).

This is the real-time replacement the design designed-for: instead of RTK Query
polling driving freshness, a socket pushes small "something changed" envelopes
and the SPA turns each into an `api.util.invalidateTags([...])` dispatch. The
frontend seam (`useLivePolling`) owns the swap; this module is just the server
side of the channel.

Transport: ``flask-sock`` (pure-Python simple-websocket -> wsproto; no native
build, ARM64-safe; no eventlet/gevent). It runs inside the normal Flask
request/app context, so ``flask.session`` is available on the upgrade request
and we can reuse the same session-cookie auth as the ``/api/*`` routes.

DEMO mode (``LAB_DATA_SOURCE`` != ``live``): emit SIMULATED events on a modest
timer so a live browser visibly updates without any lab running. This proves the
whole socket -> Redux -> UI path end-to-end.

LIVE mode: a lightweight per-connection poll loop reads the live domains via
the existing ``data_source`` accessors every ``WS_LIVE_POLL_SECONDS``, diffs
them against the last-pushed snapshot (pure logic in ``ws_live.py``), and pushes
one ``{type,event,id}`` envelope per genuinely-new anomaly / RCA record /
ingestion item. The envelope shape and the frontend seam are IDENTICAL to the
demo emitter; only the server-side producer differs. The emitter is
fail-safe: ``data_source`` accessors fall back to demo data on error, so the
loop gates on ``ws_live.looks_like_demo`` to avoid emitting a storm of fake
"new" events when live reads transiently fail (see ``ws_live`` for the full
reasoning). Set ``WS_LIVE_PUSH_ENABLED=0`` to keep the old accept-and-block
no-op behaviour.

Route hygiene: ``/ws`` is a specific rule, so Flask matches it ahead of the SPA
``<path:path>`` catch-all in ``app.py``. It does not touch ``/api/*``,
``/__reset``, ``/static``, or ``POST /login``.
"""

import json
import logging
import os
import time

from flask import session
from flask_sock import Sock
from simple_websocket import ConnectionClosed

import data_source
import ws_live

log = logging.getLogger(__name__)

# Demo emit cadence (seconds). Modest so a live browser visibly updates. Kept as
# a module constant and also readable from WS_SIM_INTERVAL so tests can shrink it
# for a fast, deterministic emit without real-time sleeps.
_DEFAULT_SIM_INTERVAL = 4.0

# The simulated event stream cycles through the three freshness domains the SPA
# cares about. Each envelope is minimal: the frontend keys off ``type`` to pick
# which RTK Query tags to invalidate; ``id`` is advisory only and coherent with
# the demo data ids (anomalies 1-5, rca 1-4).
_SIM_SEQUENCE = (
    {"type": "anomaly", "event": "updated", "id": 1},
    {"type": "ingestion", "event": "created"},
    {"type": "rca", "event": "updated", "id": 1},
)


# LIVE emitter defaults. The poll cadence is modest versus the feed's
# ~12s/~20s/~30s producers, so a few-second poll is plenty; all are env-tunable
# (consistent with how WS_SIM_INTERVAL / LAB_DATA_SOURCE are already handled).
_DEFAULT_LIVE_POLL_SECONDS = 5.0
_DEFAULT_LIVE_MAX_EMIT_PER_POLL = 50


def _sim_interval():
    """Demo emit interval in seconds (WS_SIM_INTERVAL overrides the default)."""
    try:
        return float(os.environ.get("WS_SIM_INTERVAL", _DEFAULT_SIM_INTERVAL))
    except (TypeError, ValueError):
        return _DEFAULT_SIM_INTERVAL


def _live_poll_seconds():
    """LIVE poll cadence in seconds (WS_LIVE_POLL_SECONDS overrides the default)."""
    try:
        return float(os.environ.get("WS_LIVE_POLL_SECONDS", _DEFAULT_LIVE_POLL_SECONDS))
    except (TypeError, ValueError):
        return _DEFAULT_LIVE_POLL_SECONDS


def _live_push_enabled():
    """Master enable for the LIVE emitter (WS_LIVE_PUSH_ENABLED).

    Truthy by default. When falsy (``0``/``false``/``no``/empty) the LIVE branch
    keeps today's accept-and-block no-op behaviour — a safe off-switch.
    """
    raw = os.environ.get("WS_LIVE_PUSH_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "")


def _live_max_emit():
    """Per-poll emit cap for the LIVE emitter (WS_LIVE_MAX_EMIT_PER_POLL)."""
    try:
        return int(os.environ.get("WS_LIVE_MAX_EMIT_PER_POLL", _DEFAULT_LIVE_MAX_EMIT_PER_POLL))
    except (TypeError, ValueError):
        return _DEFAULT_LIVE_MAX_EMIT_PER_POLL


def _is_live_mode():
    return os.environ.get("LAB_DATA_SOURCE", "demo") == "live"


def init_websocket(app, login_required=None):
    """Register the ``/ws`` endpoint on ``app`` and return the ``Sock``.

    ``login_required`` is accepted for parity with ``create_api_blueprint`` (the
    single source of truth for the auth decorator) but is not applied as a
    decorator here: flask-sock routes are not plain view functions, so the auth
    gate is enforced inline by checking ``session`` exactly as ``@login_required``
    does (``'user' in session``). An unauthenticated upgrade is closed before any
    event is sent, mirroring the ``/api/*`` gate.
    """
    sock = Sock(app)

    @sock.route("/ws")
    def live_push(ws):  # pragma: no cover - exercised via the WS test harness
        # Auth gate: the session cookie rides the upgrade request, so reuse the
        # same check as @login_required on /api/*. Reject unauthenticated sockets.
        if "user" not in session:
            ws.close()
            return

        # LIVE mode: push REAL lab events via a lightweight server-side poll.
        if _is_live_mode():
            # Off-switch: keep today's accept-and-block no-op when disabled.
            if not _live_push_enabled():
                try:
                    while True:
                        if ws.receive() is None:
                            break
                except ConnectionClosed:
                    pass
                return

            poll_seconds = _live_poll_seconds()
            max_emit = _live_max_emit()
            # None snapshot => the first poll seeds the baseline silently (so we
            # announce only CHANGES seen while connected, never the backlog).
            snapshot = None
            try:
                while True:
                    reads = {
                        "anomalies": data_source.get_anomalies(),
                        "rca": data_source.get_rca_records(),
                        "pm_files": data_source.get_pm_ingestion(),
                        "tickets": data_source.get_ticket_feed(),
                    }
                    # Demo-fallback gate: the data_source accessors fail-safe to
                    # demo data on any live-read error. If the read is the known
                    # demo set, treat it as a transient failure — SKIP the diff,
                    # leave the snapshot untouched, and emit NOTHING, so a blip
                    # neither storms fake events nor corrupts the live baseline.
                    # On recovery the loop diffs live-against-live (no storm).
                    if ws_live.looks_like_demo(reads):
                        time.sleep(poll_seconds)
                        continue
                    envelopes, snapshot = ws_live.diff_snapshot(snapshot, reads, max_emit)
                    for envelope in envelopes:
                        # send raises ConnectionClosed on a dead socket, ending
                        # the loop cleanly (same pattern as the demo emitter).
                        ws.send(json.dumps(envelope))
                    time.sleep(poll_seconds)
            except ConnectionClosed:
                pass
            return

        # DEMO mode: push simulated events on a modest timer. Cycle the sequence
        # so the browser sees anomaly/ingestion/rca refreshes in turn.
        interval = _sim_interval()
        i = 0
        try:
            while True:
                envelope = _SIM_SEQUENCE[i % len(_SIM_SEQUENCE)]
                ws.send(json.dumps(envelope))
                i += 1
                time.sleep(interval)
        except ConnectionClosed:
            pass

    return sock
