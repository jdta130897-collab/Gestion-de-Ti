import csv
import io
import json
import os
import re
from flask import Blueprint, request, jsonify, session, render_template, Response
from config.database import Database
from services.measurement_service import MeasurementService
from services.analytics_service import AnalyticsService
from utils.permissions import can_see_ticket, is_super_admin
from utils.release import get_evaluation_session_id
from utils.timezone import to_lima, utc_iso, utc_now

insights_bp = Blueprint('insights', __name__)
EVAL_SESSION_RE = re.compile(r'^[A-Za-z0-9._-]{1,64}$')


def _eval_phase(session_code):
    if not session_code:
        return None
    upper = session_code.upper()
    for prefix in ('PRACTICA', 'PILOTO', 'FINAL'):
        if upper.startswith(prefix + '-'):
            return prefix
    return 'OTRA'


@insights_bp.route('/api/evaluation-session', methods=['GET', 'POST'])
def evaluation_session():
    if 'user_id' not in session:
        return jsonify(error='Sesión requerida.'), 401
    env_val = os.getenv('EVALUATION_SESSION_ID', '').strip() or None
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        raw = (data.get('evaluation_session_id') or '').strip()
        if not raw:
            session.pop('evaluation_session_id', None)
        else:
            if not EVAL_SESSION_RE.match(raw):
                return jsonify(error='Formato inválido: usa 1-64 caracteres alfanuméricos, ".", "_" o "-".'), 400
            session['evaluation_session_id'] = raw
    effective = get_evaluation_session_id()
    return jsonify(
        evaluation_session_id=effective,
        phase=_eval_phase(effective),
        session_value=session.get('evaluation_session_id'),
        env_override=bool(env_val),
    )


def _sec_cell(value):
    return round(float(value) / 1000, 3) if value is not None else ''


@insights_bp.post('/api/measurements/start')
def start():
    data = request.get_json(silent=True) or {}
    try:
        attempt_id = MeasurementService.start(data.get('channel'), data.get('request_kind', 'incident'), data.get('origin_area_id'))
        return jsonify(attempt_id=attempt_id), 201
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400


@insights_bp.get('/api/analytics')
def analytics():
    try:
        summary, _ = AnalyticsService.data(request.args)
        return jsonify(summary)
    except ValueError as error:
        return jsonify(error=str(error)), 400


@insights_bp.post('/api/measurements/<attempt_id>/abandon')
def abandon(attempt_id):
    if 'user_id' not in session:
        return jsonify(error='Sesión requerida.'), 401
    data = request.get_json(silent=True) or {}
    updated = MeasurementService.abandon(attempt_id, session['user_id'], reason=data.get('reason') or 'user_abandoned')
    return jsonify(ok=True, updated=updated)


@insights_bp.post('/api/measurements/<attempt_id>/confirm')
def confirm_browser(attempt_id):
    if 'user_id' not in session:
        return jsonify(error='Sesión requerida.'), 401
    data = request.get_json(silent=True) or {}
    try:
        confirmed = MeasurementService.confirm_browser(attempt_id, session['user_id'], data)
    except ValueError as error:
        return jsonify(error=str(error)), 409
    if not confirmed:
        return jsonify(error='Medición no encontrada para esta cuenta.'), 404
    return jsonify(confirmed)


@insights_bp.get('/api/measurements/<attempt_id>/status')
def measurement_status(attempt_id):
    if 'user_id' not in session:
        return jsonify(error='Sesión requerida.'), 401
    status_data = MeasurementService.status_for_user(attempt_id, session['user_id'])
    if not status_data:
        return jsonify(error='Medición no encontrada para esta cuenta.'), 404
    return jsonify(status_data)


@insights_bp.get('/api/notifications')
def notifications():
    scope, params = AnalyticsService.ticket_scope('t')
    db = Database()
    all_unread = db.execute_query(
        '''SELECT n.id,t.created_by,t.origin_area_id,t.destination_area_id,t.assigned_to
           FROM notifications n JOIN tickets t ON t.id=n.ticket_id
           WHERE n.user_id=%s AND n.read_at IS NULL AND ''' + scope,
        [session['user_id'], *params],
    )
    unread = sum(1 for r in all_unread if can_see_ticket(r))

    rows = db.execute_query(
        '''SELECT n.*,t.created_by,t.origin_area_id,t.destination_area_id,t.assigned_to
           FROM notifications n JOIN tickets t ON t.id=n.ticket_id
           WHERE n.user_id=%s AND ''' + scope + ' ORDER BY n.created_at DESC,n.id DESC LIMIT 30',
        [session['user_id'], *params],
    )
    uid = session['user_id']
    rows = [r for r in rows if can_see_ticket(r)]
    items = []
    for r in rows[:30]:
        if r.get('assigned_to') == uid:
            scope_cat = 'assigned'
        elif r.get('created_by') == uid:
            scope_cat = 'personal'
        elif is_super_admin():
            scope_cat = 'global'
        else:
            scope_cat = 'operational_area'
        items.append({
            'id': r['id'],
            'ticket_id': r['ticket_id'],
            'kind': r.get('kind'),
            'message': r['message'],
            'scope_category': scope_cat,
            'read': r['read_at'] is not None,
            'created_at': utc_iso(r['created_at']),
        })
    return jsonify(unread=unread, items=items)


@insights_bp.post('/api/notifications/<int:notification_id>/read')
def read_notification(notification_id):
    Database().execute_update(
        'UPDATE notifications SET read_at=%s WHERE id=%s AND user_id=%s',
        (utc_now(), notification_id, session['user_id']),
    )
    return jsonify(ok=True)


@insights_bp.get('/reports/analytics.csv')
def export_csv():
    try:
        _, rows = AnalyticsService.data(request.args)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=';')
    writer.writerow([
        'Intento',
        'Reporte',
        'Área',
        'Canal',
        'Tipo',
        'Resultado',
        'Motivo resultado',
        'Inicio UTC',
        'Inicio Lima',
        'Fin servidor UTC',
        'Confirmación navegador UTC',
        'Preparación (s)',
        'Pausas (n)',
        'Pausado cliente (s)',
        'Preparación cliente (s)',
        'Procesamiento (s)',
        'Total servidor (s)',
        'Ida y vuelta navegador (s)',
        'Total navegador (s)',
        'Prioridad',
        'Estado clasificación',
        'Fuente prioridad',
        'Política',
        'Prompt',
        'Versión',
        'Participante codificado',
        'Commit',
        'Sesión evaluación',
    ])
    outcomes = {
        'started': 'Iniciado',
        'processing': 'Procesando',
        'success': 'Exitoso',
        'failed': 'Fallido',
        'abandoned': 'Abandonado',
    }
    for row in rows:
        name = row['area_name']
        if name.startswith(('=', '+', '-', '@')):
            name = "'" + name
        commit_val = row.get('build_commit') or ''
        if commit_val and row.get('commit_dirty'):
            commit_val = f'{commit_val}+dirty'
        writer.writerow([
            row['id'],
            row['ticket_id'] or '',
            name,
            'Voz' if row['channel'] == 'voice' else 'Manual',
            'Pedido' if row['request_kind'] == 'request' else 'Incidencia',
            outcomes[row['outcome']],
            row.get('outcome_reason') or '',
            utc_iso(row['started_at']) or '',
            to_lima(row['started_at']).isoformat() if row.get('started_at') else '',
            utc_iso(row.get('finished_at')) or '',
            utc_iso(row.get('client_confirmed_at')) or '',
            _sec_cell(row.get('preparation_ms')),
            row['pause_count'] if row.get('pause_count') is not None else '',
            _sec_cell(row.get('paused_ms')),
            _sec_cell(row.get('client_prep_ms')),
            _sec_cell(row.get('processing_ms')),
            _sec_cell(row.get('total_ms')),
            _sec_cell(row.get('browser_roundtrip_ms')),
            _sec_cell(row.get('browser_total_ms')),
            row.get('ticket_priority') or '',
            row.get('classification_status') or '',
            row.get('priority_source') or '',
            row.get('policy_version') or '',
            row.get('prompt_version') or '',
            row.get('software_version') or 'Sin identificar',
            row.get('participant_code') or '',
            commit_val,
            row.get('evaluation_session_id') or '',
        ])
    return Response(
        '\ufeff' + stream.getvalue(),
        content_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="mediciones-voz-vs-manual.csv"'},
    )


@insights_bp.get('/reports/analytics-bundle.json')
def export_bundle():
    try:
        bundle = AnalyticsService.reproducible_bundle(request.args)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    body = json.dumps(bundle, ensure_ascii=False, indent=2)
    headers = {'Content-Disposition': 'attachment; filename="paquete-reproducible-analitica.json"'}
    return Response(body, content_type='application/json; charset=utf-8', headers=headers)


@insights_bp.get('/reports/analytics')
def printable_report():
    try:
        summary, rows = AnalyticsService.data(request.args)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    from services.chart_export import make_svg, chart_data
    charts = [(chart_data(summary, key)[0], make_svg(summary, key)) for key in ('time', 'volume', 'success', 'phases', 'trend', 'priority', 'status')]
    html = render_template('analytics/report.html', summary=summary, rows=rows, charts=charts)
    headers = {'Content-Disposition': 'attachment; filename="informe-voz-vs-manual.html"'} if request.args.get('download') else {}
    return Response(html, content_type='text/html; charset=utf-8', headers=headers)


@insights_bp.get('/reports/chart.svg')
def svg_chart():
    try:
        summary, _ = AnalyticsService.data(request.args)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    chart = request.args.get('chart', 'time')
    if chart not in ('time', 'volume', 'success', 'phases', 'trend', 'priority', 'status'):
        return jsonify(error='Gráfico no válido.'), 400
    from services.chart_export import make_svg
    svg = make_svg(summary, chart)
    return Response(svg, content_type='image/svg+xml', headers={'Content-Disposition': f'attachment; filename="comparativa-{chart}.svg"'})
