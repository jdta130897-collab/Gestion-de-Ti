import csv
import io
from datetime import datetime
from flask import Blueprint, request, jsonify, session, render_template, Response
from config.database import Database
from services.measurement_service import MeasurementService
from services.analytics_service import AnalyticsService
from utils.permissions import can_see_ticket

insights_bp = Blueprint('insights', __name__)


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
    Database().execute_update("UPDATE creation_attempts SET outcome='abandoned',finished_at=UTC_TIMESTAMP(6) WHERE id=%s AND user_id=%s AND outcome='started'", (attempt_id, session['user_id']))
    return jsonify(ok=True)


@insights_bp.get('/api/notifications')
def notifications():
    scope, params = AnalyticsService.scope('t')
    db = Database()
    unread = db.execute_query('''SELECT COUNT(*) AS n FROM notifications n JOIN tickets t ON t.id=n.ticket_id
        WHERE n.user_id=%s AND n.read_at IS NULL AND '''+scope, [session['user_id'], *params])[0]['n']
    rows = db.execute_query('''SELECT n.*,t.created_by,t.origin_area_id FROM notifications n
        JOIN tickets t ON t.id=n.ticket_id WHERE n.user_id=%s AND '''+scope+' ORDER BY n.created_at DESC,n.id DESC LIMIT 30', [session['user_id'], *params])
    rows = [r for r in rows if can_see_ticket(r)]
    return jsonify(unread=unread, items=[{
        'id': r['id'], 'ticket_id': r['ticket_id'], 'message': r['message'],
        'read': r['read_at'] is not None, 'created_at': r['created_at'].isoformat()+'Z',
    } for r in rows[:30]])


@insights_bp.post('/api/notifications/<int:notification_id>/read')
def read_notification(notification_id):
    Database().execute_update('UPDATE notifications SET read_at=%s WHERE id=%s AND user_id=%s', (datetime.utcnow(), notification_id, session['user_id']))
    return jsonify(ok=True)


@insights_bp.get('/reports/analytics.csv')
def csv_report():
    try:
        summary, rows = AnalyticsService.data(request.args)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=';')
    writer.writerow(['Intento', 'Reporte', 'Área', 'Canal', 'Tipo', 'Resultado', 'Inicio UTC', 'Preparación (s)', 'Procesamiento (s)', 'Total (s)', 'Versión', 'Participante codificado', 'Commit'])
    outcomes = {'started':'Iniciado','processing':'Procesando','success':'Exitoso','failed':'Fallido','abandoned':'Abandonado'}
    for row in rows:
        name = row['area_name']
        if name.startswith(('=', '+', '-', '@')):
            name = "'" + name
        writer.writerow([row['id'], row['ticket_id'] or '', name, 'Voz' if row['channel']=='voice' else 'Manual', 'Pedido' if row['request_kind']=='request' else 'Incidencia', outcomes[row['outcome']], row['started_at'].isoformat(), *[round(float(row[k])/1000,3) if row[k] is not None else '' for k in ('preparation_ms','processing_ms','total_ms')],row.get('software_version') or 'Sin identificar',row.get('participant_code') or '',row.get('build_commit') or ''])
    return Response('\ufeff'+stream.getvalue(), content_type='text/csv; charset=utf-8', headers={'Content-Disposition':'attachment; filename="mediciones-voz-vs-manual.csv"'})


@insights_bp.get('/reports/analytics')
def printable_report():
    try:
        summary, rows = AnalyticsService.data(request.args)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    from services.chart_export import make_svg, chart_data
    charts = [(chart_data(summary,key)[0],make_svg(summary,key)) for key in ('time','volume','success','phases','trend','priority','status')]
    html = render_template('analytics/report.html', summary=summary, rows=rows, charts=charts)
    headers = {'Content-Disposition':'attachment; filename="informe-voz-vs-manual.html"'} if request.args.get('download') else {}
    return Response(html, content_type='text/html; charset=utf-8', headers=headers)


@insights_bp.get('/reports/chart.svg')
def svg_chart():
    try:
        summary, _ = AnalyticsService.data(request.args)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    chart = request.args.get('chart', 'time')
    if chart not in ('time','volume','success','phases','trend','priority','status'):
        return jsonify(error='Gráfico no válido.'), 400
    from services.chart_export import make_svg
    svg = make_svg(summary, chart)
    return Response(svg, content_type='image/svg+xml', headers={'Content-Disposition':f'attachment; filename="comparativa-{chart}.svg"'})
