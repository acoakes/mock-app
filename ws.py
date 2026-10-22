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

LIVE mode: the connection is accepted but emits nothing here. Wiring a real
LocalStack/Postgres/Gremlin event source is the documented follow-on (see the
module tail) — the envelope shape and the frontend seam stay identical; only the
server-side producer changes.

Route hygiene: ``/ws`` is a specific rule, so Flask matches it ahead of the SPA
``<path:path>`` catch-all in ``app.py``. It does not touch ``/api/*``,
``/__reset``, ``/static``, or ``POST /login``.
"""

import json
import os
import time

from flask import session
from flask_sock import Sock
from simple_websocket import ConnectionClosed

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


def _sim_interval():
    """Demo emit interval in seconds (WS_SIM_INTERVAL overrides the default)."""
    try:
        return float(os.environ.get("WS_SIM_INTERVAL", _DEFAULT_SIM_INTERVAL))
    except (TypeError, ValueError):
        return _DEFAULT_SIM_INTERVAL


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

        # LIVE mode: accept but emit nothing (real-lab source is the follow-on).
        # Block on receive so the connection stays open without a busy loop and
        # closes cleanly when the client goes away.
        if _is_live_mode():
            try:
                while True:
                    if ws.receive() is None:
                        break
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
