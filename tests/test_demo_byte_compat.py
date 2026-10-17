"""Demo-mode byte-compatibility gate (NFR-1 / AC-8 / MEDIUM-4).

With LAB_DATA_SOURCE unset (demo mode) the raw response bytes of GET /rca,
GET /rca/1 and GET /api/rca must equal the committed baseline captured from the
pre-change app in tests/fixtures/demo_baseline/. Any diff is a HARD failure: the
live-mode RCA subgraph visual must be invisible in demo mode down to the byte.
"""

import os
import pathlib

import pytest

import app as appmod

_BASELINE_DIR = pathlib.Path(__file__).parent / 'fixtures' / 'demo_baseline'

_CASES = [
    ('/rca', 'rca.html'),
    ('/rca/1', 'rca_1.html'),
    ('/api/rca', 'api_rca.json'),
]


@pytest.fixture
def demo_client(monkeypatch):
    monkeypatch.delenv('LAB_DATA_SOURCE', raising=False)
    client = appmod.app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = 'baseline'
    return client


@pytest.mark.parametrize('path,fname', _CASES)
def test_demo_bytes_match_committed_baseline(demo_client, path, fname):
    expected = (_BASELINE_DIR / fname).read_bytes()
    resp = demo_client.get(path)
    assert resp.status_code == 200
    assert resp.data == expected, (
        'demo bytes for %s drifted from %s baseline (NFR-1/AC-8)' % (path, fname)
    )
