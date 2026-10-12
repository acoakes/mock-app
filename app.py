import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# In-memory data stores (module-level so POST routes can mutate them)
anomalies = [
    {'id': 1, 'description': 'Spike in null values in field user_id', 'severity': 'HIGH', 'status': 'open', 'timestamp': '2024-01-15 14:32:01'},
    {'id': 2, 'description': 'Processing latency exceeded threshold', 'severity': 'MEDIUM', 'status': 'acknowledged', 'timestamp': '2024-01-15 13:20:45'},
    {'id': 3, 'description': 'Duplicate records detected in batch 4821', 'severity': 'HIGH', 'status': 'open', 'timestamp': '2024-01-15 12:05:12'},
    {'id': 4, 'description': 'Missing values in revenue field', 'severity': 'LOW', 'status': 'open', 'timestamp': '2024-01-14 09:44:33'},
    {'id': 5, 'description': 'Schema mismatch in incoming data feed', 'severity': 'MEDIUM', 'status': 'acknowledged', 'timestamp': '2024-01-14 08:15:20'},
]

rca_records = [
    {'id': 1, 'title': 'Null Value Spike Root Cause', 'status': 'resolved', 'root_cause': 'Upstream data pipeline failed validation step', 'recommendation': 'Add validation checkpoint at ingestion layer'},
    {'id': 2, 'title': 'Latency Threshold Breach Analysis', 'status': 'in_progress', 'root_cause': 'Database query not using index on timestamp column', 'recommendation': 'Add composite index on (timestamp, batch_id)'},
    {'id': 3, 'title': 'Duplicate Record Investigation', 'status': 'open', 'root_cause': 'Idempotency key not enforced in batch processor', 'recommendation': 'Implement idempotency enforcement in batch processing module'},
    {'id': 4, 'title': 'Revenue Field Data Quality Issue', 'status': 'open', 'root_cause': 'Source system sending null for optional revenue field', 'recommendation': 'Add default value handling and source system notification'},
]


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
    return render_template('dashboard.html', kpis=kpis, date_from=date_from, date_to=date_to, empty_state=empty_state)


@app.route('/anomalies')
@login_required
def anomalies_list():
    severity = request.args.get('severity', '')
    filtered = anomalies
    if severity and severity.upper() in ('HIGH', 'MEDIUM', 'LOW'):
        filtered = [a for a in anomalies if a['severity'] == severity.upper()]
    return render_template('anomalies.html', anomalies=filtered, severity=severity)


@app.route('/anomalies/<int:id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_anomaly(id):
    for anomaly in anomalies:
        if anomaly['id'] == id:
            anomaly['status'] = 'acknowledged'
            break
    return redirect(url_for('anomalies_list'))


@app.route('/anomalies/<int:id>')
@login_required
def anomaly_detail(id):
    anomaly = next((a for a in anomalies if a['id'] == id), None)
    if anomaly is None:
        return redirect(url_for('anomalies_list'))
    return render_template('anomaly_detail.html', anomaly=anomaly)


@app.route('/rca')
@login_required
def rca_list():
    status = request.args.get('status', '')
    filtered = rca_records
    if status and status in ('open', 'in_progress', 'resolved'):
        filtered = [r for r in rca_records if r['status'] == status]
    return render_template('rca.html', rca_list=filtered, status=status)


@app.route('/rca/<int:id>/update', methods=['POST'])
@login_required
def update_rca(id):
    new_status = request.form.get('status', '')
    for rca in rca_records:
        if rca['id'] == id:
            if new_status in ('open', 'in_progress', 'resolved'):
                rca['status'] = new_status
            break
    return redirect(url_for('rca_detail', id=id) + '?success=1')


@app.route('/rca/<int:id>')
@login_required
def rca_detail(id):
    rca = next((r for r in rca_records if r['id'] == id), None)
    if rca is None:
        return redirect(url_for('rca_list'))
    success = request.args.get('success')
    return render_template('rca_detail.html', rca=rca, success=success)


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
    filtered = (
        [a for a in anomalies if a['severity'] == severity]
        if severity in valid
        else list(anomalies)
    )
    return jsonify({'anomalies': filtered})


@app.route('/api/rca')
@login_required
def api_rca():
    """Return RCA records as JSON, with optional ?status= filter."""
    status = request.args.get('status', '').strip().lower()
    valid = {'open', 'in_progress', 'resolved'}
    filtered = (
        [r for r in rca_records if r['status'] == status]
        if status in valid
        else list(rca_records)
    )
    return jsonify({'records': filtered})
