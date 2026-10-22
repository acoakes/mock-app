import os
from functools import wraps
from flask import Flask, request, redirect, session, send_from_directory, abort
from flask_cors import CORS

import data_source

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Directory of the built React SPA (Vite output). Served by the catch-all below
# as the single-origin approximation of "S3 bundle + API behind one ALB".
_DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')


def _live_context():
    """Live-mode flags (demo mode -> no polling). Still read by /api/session."""
    live_mode = os.environ.get('LAB_DATA_SOURCE', 'demo') == 'live'
    try:
        refresh_seconds = int(os.environ.get('LIVE_REFRESH_SECONDS', '5') or 5)
    except (TypeError, ValueError):
        refresh_seconds = 5
    return live_mode, refresh_seconds


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # No HTML login route any more — the SPA renders /login client-side.
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['POST'])
def login():
    """Session-setting login handler (template-free).

    The HTML login UI now lives in the SPA (GET /login falls through to the
    catch-all). This POST handler is kept because the BDD API layer
    (utils/api_client.ApiClient.login) authenticates by form-POSTing here and
    reusing the session cookie; it detects failure by checking whether the
    response URL still contains '/login'. On any non-empty credential pair it
    sets the session and redirects to /dashboard; otherwise it redirects back
    to /login. No template is rendered. (The SPA's own login uses POST
    /api/login, a separate blueprint endpoint.)
    """
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    if username and password:
        session['user'] = username
        return redirect('/dashboard')
    return redirect('/login')


@app.route('/__reset', methods=['POST'])
def __reset():
    """Test-isolation hook: restore demo stores to defaults (demo mode only).

    Lets the BDD suite reset per-scenario state so demo-mode POST mutations
    (acknowledge anomaly, update RCA status) don't leak between scenarios. Not
    available in live mode, where data comes from the lab, not in-process stores.
    """
    if os.environ.get('LAB_DATA_SOURCE', 'demo') == 'live':
        return {'reset': False, 'reason': 'live mode'}, 200
    data_source.reset_demo_state()
    return {'reset': True}, 200


# ---------------------------------------------------------------------------
# JSON REST API blueprint (all /api/* endpoints live in the api/ package).
# Registered here, after login_required is defined, so the blueprint can reuse
# the single auth decorator. CORS is scoped to /api/* with credentials for the
# dev two-origin (SPA) case; the origin is configurable via SPA_ORIGIN.
# ---------------------------------------------------------------------------
from api import create_api_blueprint

app.register_blueprint(create_api_blueprint(login_required))

CORS(
    app,
    resources={r"/api/*": {"origins": [os.environ.get('SPA_ORIGIN', 'http://localhost:3000')]}},
    supports_credentials=True,
)


# ---------------------------------------------------------------------------
# SPA static serving + client-side routing fallback (design §8).
#
# This catch-all is registered LAST so the specific routes above (/api/* via
# the blueprint, /__reset, POST /login, and Flask's own /static/*) always win.
# It never handles /api/* (the blueprint owns those and 404s there rather than
# serving index.html, so a missing API path stays a JSON 404, not HTML).
# For any other path: serve the matching file under frontend/dist if it exists
# (e.g. /assets/index-*.js, /vite.svg), otherwise return index.html so the
# React BrowserRouter resolves the route (/dashboard, /rca/1, /login, ...).
# ---------------------------------------------------------------------------
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def spa(path):
    # Never let the catch-all shadow the API; the blueprint returns its own 404.
    if path == 'api' or path.startswith('api/'):
        abort(404)

    index_path = os.path.join(_DIST_DIR, 'index.html')
    if not os.path.exists(index_path):
        return (
            'SPA not built — run "npm run build" in frontend/ to generate '
            'frontend/dist.',
            503,
        )

    # Serve a real build artifact (assets, favicon, etc.) when the path maps to
    # an existing file under dist; otherwise fall through to the SPA shell.
    if path:
        candidate = os.path.join(_DIST_DIR, path)
        if os.path.isfile(candidate):
            return send_from_directory(_DIST_DIR, path)

    return send_from_directory(_DIST_DIR, 'index.html')
