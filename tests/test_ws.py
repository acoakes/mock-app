"""Tests for the WebSocket live-push channel (ws.py).

flask-sock builds a real ``simple_websocket.Server`` from ``request.environ``,
so (unlike the ``/api/*`` routes) it cannot be driven by Flask's ``test_client``
— it needs a real socket upgrade. These tests therefore split into two parts:

1. Fast, pure unit assertions on the helpers and route registration (no server).
2. Behaviour tests against a REAL threaded werkzeug server started in a
   background thread, driven by a ``simple-websocket`` client. ``WS_SIM_INTERVAL``
   is shrunk so the demo emit is observed within a short bounded wait (no
   real-time sleeps), matching the reloader-off dev invocation.

Style mirrors ``tests/test_api_endpoints.py`` (demo-reset autouse fixture,
authenticated vs anonymous clients).
"""

import json
import socket
import threading
import time

import pytest
from werkzeug.serving import make_server

import app as appmod
import data_source
import ws as wsmod
from simple_websocket import Client, ConnectionClosed


def _safe_close(client):
    """Close a WS client, ignoring an already-closed connection."""
    try:
        client.close()
    except ConnectionClosed:
        pass


@pytest.fixture(autouse=True)
def _reset_demo_state(monkeypatch):
    """Keep demo mode and reset the in-place demo stores around every test."""
    monkeypatch.delenv('LAB_DATA_SOURCE', raising=False)
    data_source.reset_demo_state()
    yield
    data_source.reset_demo_state()


# ---------------------------------------------------------------------------
# Part 1 — pure unit assertions (no server)
# ---------------------------------------------------------------------------
def test_ws_route_registered():
    """/ws is a specific websocket rule (matched ahead of the SPA catch-all)."""
    rules = [r for r in appmod.app.url_map.iter_rules() if str(r) == '/ws']
    assert len(rules) == 1
    # flask-sock marks the route as a websocket route.
    assert rules[0].websocket is True


def test_sim_interval_env_override(monkeypatch):
    monkeypatch.setenv('WS_SIM_INTERVAL', '0.05')
    assert wsmod._sim_interval() == pytest.approx(0.05)
    monkeypatch.setenv('WS_SIM_INTERVAL', 'not-a-number')
    assert wsmod._sim_interval() == wsmod._DEFAULT_SIM_INTERVAL


def test_is_live_mode(monkeypatch):
    monkeypatch.delenv('LAB_DATA_SOURCE', raising=False)
    assert wsmod._is_live_mode() is False
    monkeypatch.setenv('LAB_DATA_SOURCE', 'live')
    assert wsmod._is_live_mode() is True


def test_sim_sequence_envelopes_are_well_formed():
    """Every simulated envelope carries a known type + event the SPA can map."""
    assert wsmod._SIM_SEQUENCE
    for env in wsmod._SIM_SEQUENCE:
        assert env['type'] in {'anomaly', 'rca', 'ingestion'}
        assert env['event'] in {'created', 'updated'}


# ---------------------------------------------------------------------------
# Part 2 — behaviour against a real threaded server
# ---------------------------------------------------------------------------
def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def live_server(monkeypatch):
    """Run app on a real threaded werkzeug server in a background thread.

    Shrinks the demo emit interval so a pushed event arrives fast. Yields the
    base port; tears the server down afterwards.
    """
    monkeypatch.setenv('WS_SIM_INTERVAL', '0.05')
    port = _free_port()
    srv = make_server('127.0.0.1', port, appmod.app, threaded=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    # Give the server a moment to start accepting connections.
    time.sleep(0.2)
    try:
        yield port
    finally:
        srv.shutdown()
        thread.join(timeout=5)


def _login_cookie(port):
    """POST /api/login and return the Cookie header value for the session."""
    import http.client

    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    body = json.dumps({'username': 'u', 'password': 'p'})
    conn.request('POST', '/api/login', body=body,
                 headers={'Content-Type': 'application/json'})
    resp = conn.getresponse()
    resp.read()
    set_cookie = resp.getheader('Set-Cookie')
    conn.close()
    assert set_cookie, 'login did not set a session cookie'
    # Cookie header is just the name=value pair (strip attributes).
    return set_cookie.split(';', 1)[0]


def test_authenticated_demo_connection_receives_envelope(live_server):
    """An authenticated demo socket pushes a well-formed envelope promptly."""
    port = live_server
    cookie = _login_cookie(port)
    client = Client.connect(f'ws://127.0.0.1:{port}/ws',
                            headers={'Cookie': cookie})
    try:
        raw = client.receive(timeout=5)
        assert raw is not None, 'no event pushed within the wait'
        envelope = json.loads(raw)
        assert envelope['type'] in {'anomaly', 'rca', 'ingestion'}
        assert envelope['event'] in {'created', 'updated'}
    finally:
        _safe_close(client)


def test_unauthenticated_upgrade_is_rejected(live_server):
    """Without a session cookie the server closes the socket with no event."""
    port = live_server
    client = Client.connect(f'ws://127.0.0.1:{port}/ws')
    try:
        # The handler closes immediately; receive returns None (closed) and no
        # envelope is ever delivered.
        result = client.receive(timeout=2)
        assert result is None
    except ConnectionClosed:
        pass  # also an acceptable signal that the upgrade was rejected
    finally:
        _safe_close(client)


def test_live_mode_connection_emits_nothing(live_server, monkeypatch):
    """In live mode the socket connects but pushes no event (follow-on source)."""
    monkeypatch.setenv('LAB_DATA_SOURCE', 'live')
    port = live_server
    cookie = _login_cookie(port)
    client = Client.connect(f'ws://127.0.0.1:{port}/ws',
                            headers={'Cookie': cookie})
    try:
        result = client.receive(timeout=1)
        # No simulated events in live mode; a timeout returns None.
        assert result is None
    except (ConnectionClosed, TimeoutError):
        pass
    finally:
        _safe_close(client)
