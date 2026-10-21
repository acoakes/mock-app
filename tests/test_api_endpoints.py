"""Unit tests for the /api REST blueprint (SLICE-1 step 1).

Every endpoint is exercised with Flask's test_client in demo mode (the mode the
suite runs in), seeding session['user'] the same way test_demo_byte_compat.py
does. Each test asserts the exact JSON shape + status code from design §2/§3/§6.

Demo data anchors (data_source): DEMO_ANOMALIES ids 1-5, DEMO_RCA ids 1-4, and
get_rca_subgraph returns None in demo mode.
"""

import pytest

import app as appmod
import data_source


@pytest.fixture(autouse=True)
def _reset_demo_state(monkeypatch):
    """Keep demo mode and reset the in-place demo stores around every test so the
    acknowledge / status mutations do not leak between tests."""
    monkeypatch.delenv('LAB_DATA_SOURCE', raising=False)
    data_source.reset_demo_state()
    yield
    data_source.reset_demo_state()


@pytest.fixture
def client():
    """Authenticated demo-mode test client."""
    c = appmod.app.test_client()
    with c.session_transaction() as sess:
        sess['user'] = 't'
    return c


@pytest.fixture
def anon_client():
    """Unauthenticated test client (no session['user'])."""
    return appmod.app.test_client()


# ---------------------------------------------------------------------------
# #1 GET /api/dashboard
# ---------------------------------------------------------------------------
def test_dashboard_ok(client):
    resp = client.get('/api/dashboard')
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body['kpis']) == 5


def test_dashboard_with_date_filter_ok(client):
    resp = client.get('/api/dashboard?date_to=2099-01-01')
    assert resp.status_code == 200
    assert len(resp.get_json()['kpis']) == 5


# ---------------------------------------------------------------------------
# #2 GET /api/anomalies
# ---------------------------------------------------------------------------
def test_anomalies_list_ok(client):
    resp = client.get('/api/anomalies')
    assert resp.status_code == 200
    assert len(resp.get_json()['anomalies']) == 5


def test_anomalies_severity_filter(client):
    resp = client.get('/api/anomalies?severity=high')
    assert resp.status_code == 200
    anomalies = resp.get_json()['anomalies']
    assert anomalies and all(a['severity'] == 'HIGH' for a in anomalies)


def test_anomalies_invalid_severity_returns_all(client):
    resp = client.get('/api/anomalies?severity=bogus')
    assert resp.status_code == 200
    assert len(resp.get_json()['anomalies']) == 5


# ---------------------------------------------------------------------------
# #3 GET /api/rca
# ---------------------------------------------------------------------------
def test_rca_list_ok_and_no_rca_id(client):
    resp = client.get('/api/rca')
    assert resp.status_code == 200
    records = resp.get_json()['records']
    assert len(records) == 4
    assert all('rca_id' not in r for r in records)


def test_rca_status_filter(client):
    resp = client.get('/api/rca?status=open')
    assert resp.status_code == 200
    records = resp.get_json()['records']
    assert records and all(r['status'] == 'open' for r in records)


# ---------------------------------------------------------------------------
# #4 GET /api/ingestion
# ---------------------------------------------------------------------------
def test_ingestion_ok(client):
    resp = client.get('/api/ingestion')
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'pm_files' in body and 'tickets' in body


# ---------------------------------------------------------------------------
# #5 GET /api/charts
# ---------------------------------------------------------------------------
def test_charts_ok(client):
    resp = client.get('/api/charts')
    assert resp.status_code == 200
    body = resp.get_json()
    for key in ('by_vendor', 'by_severity', 'over_time'):
        assert 'labels' in body[key] and 'values' in body[key]


# ---------------------------------------------------------------------------
# #6 GET /api/anomalies/<id>
# ---------------------------------------------------------------------------
def test_anomaly_detail_ok(client):
    resp = client.get('/api/anomalies/1')
    assert resp.status_code == 200
    assert resp.get_json()['anomaly']['id'] == 1


def test_anomaly_detail_not_found(client):
    resp = client.get('/api/anomalies/999')
    assert resp.status_code == 404
    assert resp.get_json() == {'error': 'not_found'}


# ---------------------------------------------------------------------------
# #7 POST /api/anomalies/<id>/acknowledge
# ---------------------------------------------------------------------------
def test_acknowledge_anomaly_ok(client):
    resp = client.post('/api/anomalies/1/acknowledge')
    assert resp.status_code == 200
    assert resp.get_json() == {'id': 1, 'status': 'acknowledged'}
    follow = client.get('/api/anomalies/1')
    assert follow.get_json()['anomaly']['status'] == 'acknowledged'


def test_acknowledge_anomaly_not_found(client):
    resp = client.post('/api/anomalies/999/acknowledge')
    assert resp.status_code == 404
    assert resp.get_json() == {'error': 'not_found'}


# ---------------------------------------------------------------------------
# #8 GET /api/rca/<id>
# ---------------------------------------------------------------------------
def test_rca_detail_ok(client):
    resp = client.get('/api/rca/1')
    assert resp.status_code == 200
    assert resp.get_json()['rca']['id'] == 1


def test_rca_detail_not_found(client):
    resp = client.get('/api/rca/999')
    assert resp.status_code == 404
    assert resp.get_json() == {'error': 'not_found'}


# ---------------------------------------------------------------------------
# #9 POST /api/rca/<id>/status
# ---------------------------------------------------------------------------
def test_rca_status_update_ok(client):
    resp = client.post('/api/rca/1/status', json={'status': 'resolved'})
    assert resp.status_code == 200
    assert resp.get_json() == {'id': 1, 'status': 'resolved'}


def test_rca_status_invalid_value(client):
    resp = client.post('/api/rca/1/status', json={'status': 'bogus'})
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'invalid_status'}


def test_rca_status_missing_body(client):
    resp = client.post('/api/rca/1/status')
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'invalid_status'}


def test_rca_status_not_found_wins_over_valid_status(client):
    resp = client.post('/api/rca/999/status', json={'status': 'resolved'})
    assert resp.status_code == 404
    assert resp.get_json() == {'error': 'not_found'}


# ---------------------------------------------------------------------------
# #10 GET /api/rca/<id>/graph  (never-500 normalization)
# ---------------------------------------------------------------------------
def test_rca_graph_demo_none_normalizes_to_empty(client):
    # Demo mode: data_source.get_rca_subgraph returns None -> empty graph.
    resp = client.get('/api/rca/1/graph')
    assert resp.status_code == 200
    assert resp.get_json() == {'nodes': [], 'edges': []}


def test_rca_graph_empty_dict_normalizes_to_empty(client, monkeypatch):
    monkeypatch.setattr(data_source, 'get_rca_subgraph', lambda ui_id: {'nodes': [], 'edges': []})
    resp = client.get('/api/rca/1/graph')
    assert resp.status_code == 200
    assert resp.get_json() == {'nodes': [], 'edges': []}


def test_rca_graph_populated_passes_through(client, monkeypatch):
    populated = {
        'nodes': [{'id': 'anomaly:1', 'type': 'anomaly', 'label': 'a', 'props': {}}],
        'edges': [{'from': 'anomaly:1', 'to': 'rc:1', 'type': 'caused_by', 'props': {}}],
    }
    monkeypatch.setattr(data_source, 'get_rca_subgraph', lambda ui_id: populated)
    resp = client.get('/api/rca/1/graph')
    assert resp.status_code == 200
    assert resp.get_json() == populated


# ---------------------------------------------------------------------------
# #11a POST /api/login
# ---------------------------------------------------------------------------
def test_login_ok(anon_client):
    resp = anon_client.post('/api/login', json={'username': 'u', 'password': 'p'})
    assert resp.status_code == 200
    assert resp.get_json() == {'authenticated': True, 'user': 'u'}


def test_login_empty_password(anon_client):
    resp = anon_client.post('/api/login', json={'username': 'u', 'password': ''})
    assert resp.status_code == 401
    assert resp.get_json() == {'authenticated': False, 'error': 'invalid_credentials'}


# ---------------------------------------------------------------------------
# #11b GET /api/session
# ---------------------------------------------------------------------------
def test_session_authenticated_demo(client):
    resp = client.get('/api/session')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['authenticated'] is True
    assert body['user'] == 't'
    assert body['mode'] == 'demo'
    assert body['refresh_seconds'] == 5


def test_session_authenticated_live_mode(client, monkeypatch):
    monkeypatch.setenv('LAB_DATA_SOURCE', 'live')
    resp = client.get('/api/session')
    assert resp.status_code == 200
    assert resp.get_json()['mode'] == 'live'


def test_session_unauthenticated(anon_client):
    resp = anon_client.get('/api/session')
    assert resp.status_code == 401
    assert resp.get_json() == {'authenticated': False}


# ---------------------------------------------------------------------------
# #11c POST /api/logout
# ---------------------------------------------------------------------------
def test_logout_clears_session(client):
    resp = client.post('/api/logout')
    assert resp.status_code == 200
    assert resp.get_json() == {'authenticated': False}
    follow = client.get('/api/session')
    assert follow.status_code == 401


# ---------------------------------------------------------------------------
# Auth gate: unauthenticated data endpoint redirects to /login (302)
# ---------------------------------------------------------------------------
def test_unauthenticated_data_endpoint_redirects(anon_client):
    resp = anon_client.get('/api/dashboard')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


# ---------------------------------------------------------------------------
# CORS: preflight carries the configured SPA origin + credentials
# ---------------------------------------------------------------------------
def test_cors_preflight_headers(client):
    resp = client.open(
        '/api/dashboard',
        method='OPTIONS',
        headers={
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
        },
    )
    assert resp.headers.get('Access-Control-Allow-Origin') == 'http://localhost:3000'
    assert resp.headers.get('Access-Control-Allow-Credentials') == 'true'
