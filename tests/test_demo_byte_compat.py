"""Demo-mode byte-compatibility gate (NFR-1 / AC-8 / MEDIUM-4).

With LAB_DATA_SOURCE unset (demo mode) the raw response bytes of GET /api/rca
must equal the committed baseline in tests/fixtures/demo_baseline/. Any diff is
a HARD failure.

The two HTML baseline cases (/rca, /rca/1) were removed at the SPA cut-over
(slice 1 step 7): those Jinja routes no longer exist, so there is no server HTML
to keep byte-stable. The /api/rca JSON case persists as an API-shape regression
test. Its fixture is pinned to LF via tests/fixtures/demo_baseline/.gitattributes
so the committed baseline matches the LF bytes Flask emits (avoids the Windows
autocrlf CRLF-vs-LF drift).
"""

import os
import pathlib

import pytest

import app as appmod

_BASELINE_DIR = pathlib.Path(__file__).parent / 'fixtures' / 'demo_baseline'

_CASES = [
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
