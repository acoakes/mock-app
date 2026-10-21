import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session

import data_source

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')


def _live_context():
    """Live-mode flags for the auto-refreshing pages (demo mode -> no refresh)."""
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
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username and password:
            session['user'] = username
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    kpis = [
        {'name': 'Throughput', 'value': '94.2', 'unit': '%'},
        {'name': 'Data Quality Score', 'value': '87.5', 'unit': '%'},
        {'name': 'Anomaly Rate', 'value': '3.1', 'unit': '%'},
        {'name': 'Processing Latency', 'value': '142', 'unit': 'ms'},
        {'name': 'Records Processed', 'value': '1,284,302', 'unit': ''},
    ]
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    empty_state = False
    if date_to:
        try:
            year = int(date_to.split('-')[0])
            if year > 2030:
                empty_state = True
        except (ValueError, IndexError):
            pass
    live_mode, refresh_seconds = _live_context()
    return render_template('dashboard.html', kpis=kpis, date_from=date_from, date_to=date_to, empty_state=empty_state, live_mode=live_mode, refresh_seconds=refresh_seconds)


@app.route('/anomalies')
@login_required
def anomalies_list():
    severity = request.args.get('severity', '')
    all_anomalies = data_source.get_anomalies()
    filtered = all_anomalies
    if severity and severity.upper() in ('HIGH', 'MEDIUM', 'LOW'):
        filtered = [a for a in all_anomalies if a['severity'] == severity.upper()]
    live_mode, refresh_seconds = _live_context()
    return render_template('anomalies.html', anomalies=filtered, severity=severity, live_mode=live_mode, refresh_seconds=refresh_seconds)


@app.route('/anomalies/<int:id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_anomaly(id):
    data_source.set_anomaly_status(id, 'acknowledged')
    return redirect(url_for('anomalies_list'))


@app.route('/anomalies/<int:id>')
@login_required
def anomaly_detail(id):
    anomaly = next((a for a in data_source.get_anomalies() if a['id'] == id), None)
    if anomaly is None:
        return redirect(url_for('anomalies_list'))
    return render_template('anomaly_detail.html', anomaly=anomaly)


@app.route('/rca')
@login_required
def rca_list():
    status = request.args.get('status', '')
    all_records = data_source.get_rca_records()
    filtered = all_records
    if status and status in ('open', 'in_progress', 'resolved'):
        filtered = [r for r in all_records if r['status'] == status]
    live_mode, refresh_seconds = _live_context()
    return render_template('rca.html', rca_list=filtered, status=status, live_mode=live_mode, refresh_seconds=refresh_seconds)


@app.route('/rca/<int:id>/update', methods=['POST'])
@login_required
def update_rca(id):
    new_status = request.form.get('status', '')
    if new_status in ('open', 'in_progress', 'resolved'):
        data_source.set_rca_status(id, new_status)
    return redirect(url_for('rca_detail', id=id) + '?success=1')


@app.route('/rca/<int:id>')
@login_required
def rca_detail(id):
    rca = next((r for r in data_source.get_rca_records() if r['id'] == id), None)
    if rca is None:
        return redirect(url_for('rca_list'))
    success = request.args.get('success')
    live_mode, _ = _live_context()
    rca_graph = data_source.get_rca_subgraph(id) if live_mode else None
    return render_template('rca_detail.html', rca=rca, success=success, live_mode=live_mode, rca_graph=rca_graph)


@app.route('/ingestion')
@login_required
def ingestion():
    pm_files = data_source.get_pm_ingestion()
    tickets = data_source.get_ticket_feed()
    live_mode, refresh_seconds = _live_context()
    return render_template(
        'ingestion.html',
        pm_files=pm_files,
        tickets=tickets,
        live_mode=live_mode,
        refresh_seconds=refresh_seconds,
    )


# ---------------------------------------------------------------------------
# JSON API endpoints (used by automated API tests)
# ---------------------------------------------------------------------------
from flask import jsonify


@app.route('/api/dashboard')
@login_required
def api_dashboard():
    """Return KPI metrics as JSON."""
    kpis = [
        {'name': 'Throughput', 'value': '94.2', 'unit': '%'},
        {'name': 'Data Quality Score', 'value': '87.5', 'unit': '%'},
        {'name': 'Anomaly Rate', 'value': '3.1', 'unit': '%'},
        {'name': 'Processing Latency', 'value': '142', 'unit': 'ms'},
        {'name': 'Records Processed', 'value': '1,284,302', 'unit': ''},
    ]
    return jsonify({'kpis': kpis})


@app.route('/api/anomalies')
@login_required
def api_anomalies():
    """Return anomalies as JSON, with optional ?severity= filter."""
    severity = request.args.get('severity', '').strip().upper()
    valid = {'HIGH', 'MEDIUM', 'LOW'}
    all_anomalies = data_source.get_anomalies()
    filtered = (
        [a for a in all_anomalies if a['severity'] == severity]
        if severity in valid
        else list(all_anomalies)
    )
    return jsonify({'anomalies': filtered})


@app.route('/api/rca')
@login_required
def api_rca():
    """Return RCA records as JSON, with optional ?status= filter."""
    status = request.args.get('status', '').strip().lower()
    valid = {'open', 'in_progress', 'resolved'}
    all_records = data_source.get_rca_records()
    filtered = (
        [r for r in all_records if r['status'] == status]
        if status in valid
        else list(all_records)
    )
    return jsonify({'records': filtered})


@app.route('/api/ingestion')
@login_required
def api_ingestion():
    """Return the live ingestion feed (PM files + tickets) as JSON."""
    return jsonify({
        'pm_files': data_source.get_pm_ingestion(),
        'tickets': data_source.get_ticket_feed(),
    })
