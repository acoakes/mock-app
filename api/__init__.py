"""Pure-JSON REST API blueprint (SLICE-1 step 1).

A thin JSON layer over ``data_source`` that runs IN PARALLEL with the existing
Jinja HTML routes in ``app.py``. All 11 endpoints from the design live here under
the ``/api`` prefix. The data layer (``data_source.py``) owns the live/demo split,
the fail-safe fallback to demo data and all byte-identical-demo contracts; the API
only serializes what it returns.

The 4 pre-existing endpoints (GET /api/dashboard, /api/anomalies, /api/rca,
/api/ingestion) keep their exact response shapes (the BDD API layer depends on
them). The 7 new endpoints are per the approved design §2 / §3 / §6.

``login_required`` is passed in from ``app`` (where it is defined) so there is a
single source of truth for the auth decorator and no circular import at module
load. ``app._live_context`` is imported lazily inside ``/api/session`` for the
same reason.
"""

import logging

from flask import Blueprint, jsonify, request, session

import data_source

log = logging.getLogger(__name__)

_VALID_SEVERITIES = {'HIGH', 'MEDIUM', 'LOW'}
_VALID_RCA_STATUSES = {'open', 'in_progress', 'resolved'}


def create_api_blueprint(login_required):
    """Build the ``/api`` blueprint.

    ``login_required`` is the decorator defined in ``app.py``; it is injected so
    the blueprint does not import ``app`` at module load (which would create a
    circular import, since ``app`` imports this factory).
    """
    api_bp = Blueprint('api', __name__, url_prefix='/api')

    # ------------------------------------------------------------------
    # Existing endpoints (shapes kept byte-identical for the BDD API layer)
    # ------------------------------------------------------------------
    @api_bp.route('/dashboard')
    @login_required
    def api_dashboard():
        """Return KPI metrics as JSON, with optional ?date_from=&date_to= filter."""
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        return jsonify({'kpis': data_source.get_dashboard_kpis(date_from, date_to)})

    @api_bp.route('/anomalies')
    @login_required
    def api_anomalies():
        """Return anomalies as JSON, with optional ?severity= filter."""
        severity = request.args.get('severity', '').strip().upper()
        all_anomalies = data_source.get_anomalies()
        filtered = (
            [a for a in all_anomalies if a['severity'] == severity]
            if severity in _VALID_SEVERITIES
            else list(all_anomalies)
        )
        return jsonify({'anomalies': filtered})

    @api_bp.route('/rca')
    @login_required
    def api_rca():
        """Return RCA records as JSON, with optional ?status= filter."""
        status = request.args.get('status', '').strip().lower()
        all_records = data_source.get_rca_records()
        filtered = (
            [r for r in all_records if r['status'] == status]
            if status in _VALID_RCA_STATUSES
            else list(all_records)
        )
        return jsonify({'records': filtered})

    @api_bp.route('/ingestion')
    @login_required
    def api_ingestion():
        """Return the ingestion feed (PM files + tickets) as JSON."""
        return jsonify({
            'pm_files': data_source.get_pm_ingestion(),
            'tickets': data_source.get_ticket_feed(),
        })

    # ------------------------------------------------------------------
    # New data endpoints
    # ------------------------------------------------------------------
    @api_bp.route('/charts')
    @login_required
    def api_charts():
        """Return the dashboard chart datasets, with the same date filter as /dashboard."""
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        return jsonify(data_source.get_anomaly_charts(date_from, date_to))

    @api_bp.route('/anomalies/<int:id>')
    @login_required
    def api_anomaly_detail(id):
        """Return a single anomaly, or 404 if there is no anomaly with that id."""
        anomaly = next((a for a in data_source.get_anomalies() if a['id'] == id), None)
        if anomaly is None:
            return jsonify({'error': 'not_found'}), 404
        return jsonify({'anomaly': anomaly})

    @api_bp.route('/anomalies/<int:id>/acknowledge', methods=['POST'])
    @login_required
    def api_acknowledge_anomaly(id):
        """Acknowledge an anomaly; 404 if the id does not exist."""
        exists = any(a['id'] == id for a in data_source.get_anomalies())
        if not exists:
            return jsonify({'error': 'not_found'}), 404
        data_source.set_anomaly_status(id, 'acknowledged')
        return jsonify({'id': id, 'status': 'acknowledged'})

    @api_bp.route('/rca/<int:id>')
    @login_required
    def api_rca_detail(id):
        """Return a single RCA record, or 404 if there is no record with that id."""
        rca = next((r for r in data_source.get_rca_records() if r['id'] == id), None)
        if rca is None:
            return jsonify({'error': 'not_found'}), 404
        return jsonify({'rca': rca})

    @api_bp.route('/rca/<int:id>/status', methods=['POST'])
    @login_required
    def api_rca_status(id):
        """Update an RCA record's status.

        404 if the id does not exist (checked first); 400 on a bad/missing status.
        """
        exists = any(r['id'] == id for r in data_source.get_rca_records())
        if not exists:
            return jsonify({'error': 'not_found'}), 404
        body = request.get_json(silent=True) or {}
        status = body.get('status')
        if status not in _VALID_RCA_STATUSES:
            return jsonify({'error': 'invalid_status'}), 400
        data_source.set_rca_status(id, status)
        return jsonify({'id': id, 'status': status})

    @api_bp.route('/rca/<int:id>/graph')
    @login_required
    def api_rca_graph(id):
        """Return the RCA subgraph for the Cytoscape view.

        Both the ``None`` case (demo / unresolved id / lab outage) and the empty
        ``{nodes:[],edges:[]}`` case normalize to an empty graph, so a lab outage
        never 500s (FR-13). A populated live subgraph passes through unchanged.
        """
        subgraph = data_source.get_rca_subgraph(id)
        if not subgraph or not subgraph.get('nodes'):
            return jsonify({'nodes': [], 'edges': []})
        return jsonify(subgraph)

    # ------------------------------------------------------------------
    # Auth / session (not login_required; /session handles its own 401)
    # ------------------------------------------------------------------
    @api_bp.route('/login', methods=['POST'])
    def api_login():
        """Establish the session cookie. Any non-empty username+password passes."""
        body = request.get_json(silent=True) or {}
        username = (body.get('username') or '').strip()
        password = (body.get('password') or '').strip()
        if username and password:
            session['user'] = username
            return jsonify({'authenticated': True, 'user': username})
        return jsonify({'authenticated': False, 'error': 'invalid_credentials'}), 401

    @api_bp.route('/session')
    def api_session():
        """Let the SPA rehydrate auth + mode on reload without a redirect."""
        user = session.get('user')
        if not user:
            return jsonify({'authenticated': False}), 401
        # Lazy import to avoid a circular import at module load.
        import app as appmod
        live_mode, refresh_seconds = appmod._live_context()
        return jsonify({
            'authenticated': True,
            'user': user,
            'mode': 'live' if live_mode else 'demo',
            'refresh_seconds': refresh_seconds,
        })

    @api_bp.route('/logout', methods=['POST'])
    def api_logout():
        """Clear the session."""
        session.clear()
        return jsonify({'authenticated': False})

    # ------------------------------------------------------------------
    # Blueprint-level catch-all for unexpected route exceptions -> 500.
    # The data layer already swallows backend failures and falls back to demo
    # data, so lab outages do not reach here.
    # ------------------------------------------------------------------
    @api_bp.errorhandler(Exception)
    def api_internal_error(exc):
        from werkzeug.exceptions import HTTPException

        # Let Flask's own HTTP errors (404/405/...) keep their status + shape.
        if isinstance(exc, HTTPException):
            return exc
        log.error('Unhandled exception in /api route: %s', exc, exc_info=True)
        return jsonify({'error': 'internal'}), 500

    return api_bp
