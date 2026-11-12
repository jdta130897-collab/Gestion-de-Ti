from datetime import datetime, timedelta
from functools import wraps
from time import perf_counter
import uuid
from flask import request, session, g, jsonify, redirect, url_for, flash
from config.database import Database
from services.area_service import AreaService


def utcnow():
    return datetime.utcnow()


class MeasurementService:
    @staticmethod
    def start(channel, kind, origin=None):
        if channel not in ('manual', 'voice') or kind not in ('incident', 'request'):
            raise ValueError('Canal o tipo de solicitud no válido.')
        area_id = session['area_id']
        if session['user_role'] == 'super_admin' and origin:
            area_id = int(origin)
        area = AreaService.get(area_id)
        if not area or not area['is_active']:
            raise ValueError('Selecciona un área activa.')
        db = Database()
        # Reiniciar un intento significa abandonar el anterior, no contar un éxito.
        db.execute_update("UPDATE creation_attempts SET outcome='abandoned',finished_at=%s WHERE user_id=%s AND channel=%s AND outcome='started'", (utcnow(), session['user_id'], channel))
        attempt_id = str(uuid.uuid4())
        db.execute_update('INSERT INTO creation_attempts (id,user_id,origin_area_id,channel,request_kind,started_at) VALUES (%s,%s,%s,%s,%s,%s)', (attempt_id, session['user_id'], area_id, channel, kind, utcnow()))
        return attempt_id

    @staticmethod
    def begin(attempt_id, channel):
        db = Database()
        rows = db.execute_query('SELECT * FROM creation_attempts WHERE id=%s AND user_id=%s AND channel=%s', (attempt_id, session['user_id'], channel))
        if not rows:
            raise ValueError('El temporizador no pertenece a esta sesión. Inicia una nueva medición.')
        row = rows[0]
        if row['outcome'] == 'success':
            return row
        if row['outcome'] != 'started' or utcnow() - row['started_at'] > timedelta(hours=2):
            raise ValueError('La medición ya se envió o expiró. Inicia una nueva medición.')
        now = utcnow()
        changed = db.execute_update("UPDATE creation_attempts SET outcome='processing',submitted_at=%s,preparation_ms=%s WHERE id=%s AND outcome='started'", (now, (now-row['started_at']).total_seconds()*1000, attempt_id))
        if not changed:
            raise ValueError('La solicitud ya se está procesando; espera la confirmación.')
        return row

    @staticmethod
    def finish(attempt_id, elapsed, ticket_id=None):
        db = Database()
        now = utcnow()
        area, kind, words = None, None, None
        if ticket_id:
            ticket = db.execute_query('SELECT origin_area_id,request_kind,description FROM tickets WHERE id=%s', (ticket_id,))[0]
            area, kind, words = ticket['origin_area_id'], ticket['request_kind'], len(ticket['description'].split())
        db.execute_update('''UPDATE creation_attempts SET finished_at=%s,outcome=%s,processing_ms=%s,
            total_ms=TIMESTAMPDIFF(MICROSECOND,started_at,%s)/1000,ticket_id=%s,
            origin_area_id=COALESCE(%s,origin_area_id),request_kind=COALESCE(%s,request_kind),word_count=%s
            WHERE id=%s AND user_id=%s AND outcome='processing' ''',
            (now, 'success' if ticket_id else 'failed', elapsed*1000, now, ticket_id, area, kind, words, attempt_id, session['user_id']))
        return db.execute_query('SELECT total_ms FROM creation_attempts WHERE id=%s', (attempt_id,))[0]['total_ms']


def measure_submission(channel):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if request.method != 'POST':
                return function(*args, **kwargs)
            attempt_id = request.form.get('attempt_id')
            # Clientes anteriores siguen operando, pero sus tiempos no se inventan.
            if not attempt_id:
                return function(*args, **kwargs)
            try:
                row = MeasurementService.begin(attempt_id, channel)
            except (ValueError, TypeError) as error:
                if channel == 'voice':
                    return jsonify(error=str(error)), 409
                flash(str(error), 'warning')
                return redirect(url_for('create_ticket'))
            if row['outcome'] == 'success':
                if not row['ticket_id']:
                    return jsonify(error='El reporte de esta medición ya no existe.'), 409
                if channel == 'voice':
                    return jsonify(mensaje='Reporte ya registrado', ticket_id=row['ticket_id'], total_ms=row['total_ms']), 200
                return redirect(url_for('view_ticket', ticket_id=row['ticket_id']))
            started = perf_counter()
            g.created_ticket_id = None
            try:
                result = function(*args, **kwargs)
            except Exception:
                MeasurementService.finish(attempt_id, perf_counter()-started)
                raise
            total = MeasurementService.finish(attempt_id, perf_counter()-started, g.created_ticket_id)
            if g.created_ticket_id:
                if channel == 'manual':
                    flash(f'Registro manual completado en {total/1000:.1f} segundos.', 'success')
                else:
                    response, status = result if isinstance(result, tuple) else (result, 200)
                    data = response.get_json()
                    data['total_ms'] = total
                    return jsonify(data), status
            return result
        return wrapped
    return decorate
