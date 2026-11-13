from datetime import timedelta
from functools import wraps
from time import perf_counter
import uuid
from flask import request, session, g, jsonify, redirect, url_for, flash
from config.database import Database
from services.area_service import AreaService
from services.participant_service import ParticipantService
from utils.release import get_evaluation_session_id, get_release_metadata
from utils.timezone import utc_iso, utc_now


def utcnow():
    return utc_now()


STARTED_EXPIRY_SECONDS = 7200
PROCESSING_STALE_SECONDS = 600


def _non_negative_float(value, maximum=86_400_000.0):
    if value is None or value == '':
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or parsed > maximum:
        return None
    return round(parsed, 3)


def _non_negative_int(value, maximum=10_000):
    if value is None or value == '':
        return None
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    if parsed < 0 or parsed > maximum:
        return None
    return parsed


class MeasurementBusyError(ValueError):
    """Indica que la misma medición sigue procesándose en el servidor."""


class MeasurementService:
    @staticmethod
    def sweep_stale(db=None):
        """Clasifica intentos vencidos sin inventar duraciones: >2h en started -> abandoned; >10min en processing sin ticket -> failed."""
        db = db or Database()
        now = utc_now()
        started_cutoff = now - timedelta(seconds=STARTED_EXPIRY_SECONDS)
        processing_cutoff = now - timedelta(seconds=PROCESSING_STALE_SECONDS)
        db.execute_update(
            "UPDATE creation_attempts SET outcome='abandoned',outcome_reason='expired_started',finished_at=%s "
            "WHERE outcome='started' AND started_at < %s",
            (now, started_cutoff),
        )
        db.execute_update(
            "UPDATE creation_attempts SET outcome='failed',outcome_reason='stale_processing_timeout',finished_at=%s "
            "WHERE outcome='processing' AND ticket_id IS NULL AND COALESCE(submitted_at, started_at) < %s",
            (now, processing_cutoff),
        )

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
        ParticipantService.ensure_for_user(session['user_id'])
        release = get_release_metadata()
        db = Database()
        now = utc_now()
        # Reiniciar un intento significa abandonar el anterior, no contar un éxito.
        db.execute_update(
            "UPDATE creation_attempts SET outcome='abandoned',outcome_reason='restarted_by_user',finished_at=%s "
            "WHERE user_id=%s AND channel=%s AND outcome='started'",
            (now, session['user_id'], channel),
        )
        attempt_id = str(uuid.uuid4())
        db.execute_update(
            'INSERT INTO creation_attempts (id,user_id,origin_area_id,channel,request_kind,started_at,software_version,build_commit,commit_dirty,evaluation_session_id) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (
                attempt_id,
                session['user_id'],
                area_id,
                channel,
                kind,
                now,
                release['version'],
                release['commit'] or None,
                release['dirty'],
                get_evaluation_session_id(),
            ),
        )
        return attempt_id

    @staticmethod
    def abandon(attempt_id, user_id, reason='user_abandoned'):
        allowed_reasons = {'user_abandoned', 'mic_permission_denied', 'connection_cancelled'}
        safe_reason = reason if reason in allowed_reasons else 'user_abandoned'
        db = Database()
        return db.execute_update(
            "UPDATE creation_attempts SET outcome='abandoned',outcome_reason=%s,finished_at=%s "
            "WHERE id=%s AND user_id=%s AND outcome='started'",
            (safe_reason, utc_now(), attempt_id, user_id),
        )

    @staticmethod
    def begin(attempt_id, channel, client_metrics=None):
        db = Database()
        rows = db.execute_query(
            'SELECT * FROM creation_attempts WHERE id=%s AND user_id=%s AND channel=%s',
            (attempt_id, session['user_id'], channel),
        )
        if not rows:
            raise ValueError('El temporizador no pertenece a esta sesión. Inicia una nueva medición.')
        row = rows[0]
        if row['outcome'] == 'success':
            return row
        if row['outcome'] == 'processing':
            ref_time = row.get('submitted_at') or row['started_at']
            if utc_now() - ref_time > timedelta(seconds=PROCESSING_STALE_SECONDS) and not row.get('ticket_id'):
                db.execute_update(
                    "UPDATE creation_attempts SET outcome='failed',outcome_reason='stale_processing_timeout',finished_at=%s "
                    "WHERE id=%s AND outcome='processing' AND ticket_id IS NULL",
                    (utc_now(), attempt_id),
                )
                raise ValueError('El intento previo superó el tiempo límite en procesamiento sin guardar ticket. Inicia una nueva medición.')
            raise MeasurementBusyError('La solicitud ya se está procesando en el servidor; espera la confirmación sin duplicar.')
        if row['outcome'] != 'started':
            raise ValueError('La medición ya concluyó o fue cancelada. Inicia una nueva medición.')
        if utc_now() - row['started_at'] > timedelta(seconds=STARTED_EXPIRY_SECONDS):
            db.execute_update(
                "UPDATE creation_attempts SET outcome='abandoned',outcome_reason='expired_started',finished_at=%s "
                "WHERE id=%s AND outcome='started'",
                (utc_now(), attempt_id),
            )
            raise ValueError('La medición expiró por inactividad previa al envío. Inicia una nueva medición.')
        now = utc_now()
        metrics = client_metrics or {}
        pause_count = _non_negative_int(metrics.get('pause_count'))
        paused_ms = _non_negative_float(metrics.get('paused_ms'))
        client_prep_ms = _non_negative_float(metrics.get('client_prep_ms'))
        prep_ms = (now - row['started_at']).total_seconds() * 1000
        if paused_ms is not None and paused_ms > prep_ms + 5000:
            paused_ms = round(prep_ms, 3)
        changed = db.execute_update(
            "UPDATE creation_attempts SET outcome='processing',submitted_at=%s,preparation_ms=%s,"
            "pause_count=%s,paused_ms=%s,client_prep_ms=%s WHERE id=%s AND outcome='started'",
            (now, prep_ms, pause_count, paused_ms, client_prep_ms, attempt_id),
        )
        if not changed:
            latest = db.execute_query(
                'SELECT * FROM creation_attempts WHERE id=%s AND user_id=%s AND channel=%s',
                (attempt_id, session['user_id'], channel),
            )
            if latest:
                if latest[0]['outcome'] == 'success':
                    return latest[0]
                if latest[0]['outcome'] == 'processing':
                    raise MeasurementBusyError('La solicitud ya se está procesando en el servidor; espera la confirmación sin duplicar.')
            raise ValueError('La medición ya se envió o expiró. Inicia una nueva medición.')
        return row

    @staticmethod
    def finish_in_tx(tx, attempt_id, user_id, elapsed, ticket_id, area_id, kind, words):
        now = utc_now()
        release = get_release_metadata()
        changed = tx.execute(
            '''UPDATE creation_attempts SET finished_at=%s,outcome=%s,outcome_reason=%s,processing_ms=%s,
               total_ms=TIMESTAMPDIFF(MICROSECOND,started_at,%s)/1000,ticket_id=%s,
               origin_area_id=COALESCE(%s,origin_area_id),request_kind=COALESCE(%s,request_kind),
               word_count=%s,build_commit=COALESCE(build_commit,%s),
               commit_dirty=COALESCE(commit_dirty,%s),
               evaluation_session_id=COALESCE(evaluation_session_id,%s)
               WHERE id=%s AND user_id=%s AND outcome='processing' ''',
            (
                now,
                'success',
                'completed',
                elapsed * 1000,
                now,
                ticket_id,
                area_id,
                kind,
                words,
                release['commit'] or None,
                release['dirty'],
                get_evaluation_session_id(),
                attempt_id,
                user_id,
            ),
        )
        if not changed:
            return 0, None
        total = tx.query('SELECT total_ms FROM creation_attempts WHERE id=%s', (attempt_id,))[0]['total_ms']
        return changed, total

    @staticmethod
    def finish(attempt_id, elapsed, ticket_id=None, reason=None):
        db = Database()
        now = utc_now()
        area, kind, words = None, None, None
        if ticket_id:
            ticket = db.execute_query('SELECT origin_area_id,request_kind,description FROM tickets WHERE id=%s', (ticket_id,))[0]
            area, kind, words = ticket['origin_area_id'], ticket['request_kind'], len(ticket['description'].split())
            outcome = 'success'
            outcome_reason = reason or 'completed'
        else:
            outcome = 'failed'
            outcome_reason = (reason or 'processing_failed')[:60]
        db.execute_update(
            '''UPDATE creation_attempts SET finished_at=%s,outcome=%s,outcome_reason=%s,processing_ms=%s,
               total_ms=TIMESTAMPDIFF(MICROSECOND,started_at,%s)/1000,ticket_id=%s,
               origin_area_id=COALESCE(%s,origin_area_id),request_kind=COALESCE(%s,request_kind),word_count=%s
               WHERE id=%s AND user_id=%s AND outcome='processing' ''',
            (now, outcome, outcome_reason, elapsed * 1000, now, ticket_id, area, kind, words, attempt_id, session['user_id']),
        )
        rows = db.execute_query('SELECT total_ms FROM creation_attempts WHERE id=%s', (attempt_id,))
        return rows[0]['total_ms'] if rows else None

    @staticmethod
    def confirm_browser(attempt_id, user_id, payload=None):
        """Registra la confirmación visible recibida por el navegador sin alterar los tiempos del servidor."""
        db = Database()
        rows = db.execute_query(
            'SELECT id, outcome, ticket_id, outcome_reason, client_confirmed_at FROM creation_attempts WHERE id=%s AND user_id=%s',
            (attempt_id, user_id),
        )
        if not rows:
            return None
        row = rows[0]
        if row['outcome'] != 'success' or not row['ticket_id']:
            raise ValueError('Solo pueden confirmarse en navegador intentos persistidos con ticket.')
        data = payload or {}
        roundtrip_ms = _non_negative_float(data.get('browser_roundtrip_ms'))
        browser_total_ms = _non_negative_float(data.get('browser_total_ms'))
        recovered = bool(data.get('recovered_from_status'))
        now = utc_now()
        next_reason = (
            'recovered_after_lost_response'
            if recovered and (row.get('outcome_reason') in (None, 'completed'))
            else row.get('outcome_reason')
        )
        db.execute_update(
            '''UPDATE creation_attempts
               SET client_confirmed_at=COALESCE(client_confirmed_at,%s),
                   browser_roundtrip_ms=COALESCE(browser_roundtrip_ms,%s),
                   browser_total_ms=COALESCE(browser_total_ms,%s),
                   outcome_reason=%s
               WHERE id=%s AND user_id=%s AND outcome='success' ''',
            (now, roundtrip_ms, browser_total_ms, next_reason, attempt_id, user_id),
        )
        updated = db.execute_query(
            'SELECT id, client_confirmed_at, browser_roundtrip_ms, browser_total_ms, outcome_reason FROM creation_attempts WHERE id=%s',
            (attempt_id,),
        )[0]
        return {
            'attempt_id': updated['id'],
            'browser_confirmed': updated['client_confirmed_at'] is not None,
            'client_confirmed_at': utc_iso(updated['client_confirmed_at']),
            'browser_roundtrip_ms': updated['browser_roundtrip_ms'],
            'browser_total_ms': updated['browser_total_ms'],
            'outcome_reason': updated['outcome_reason'],
        }

    @staticmethod
    def _replay_details(db, row):
        tickets = db.execute_query('SELECT id,request_kind,priority FROM tickets WHERE id=%s', (row['ticket_id'],))
        if not tickets:
            return None
        t = tickets[0]
        snaps = db.execute_query(
            'SELECT classification_status,priority_source,has_mixed_requests FROM classification_snapshots WHERE ticket_id=%s ORDER BY created_at ASC LIMIT 1',
            (t['id'],),
        )
        snap = snaps[0] if snaps else {}
        return {
            'ticket_id': t['id'],
            'request_kind': t['request_kind'],
            'priority': t['priority'],
            'classification_status': snap.get('classification_status'),
            'priority_source': snap.get('priority_source'),
            'has_mixed_requests': bool(snap.get('has_mixed_requests', False)),
        }

    @classmethod
    def status_for_user(cls, attempt_id, user_id):
        db = Database()
        cls.sweep_stale(db)
        rows = db.execute_query(
            'SELECT id,channel,outcome,outcome_reason,ticket_id,preparation_ms,processing_ms,total_ms,'
            'client_confirmed_at,browser_roundtrip_ms,browser_total_ms,started_at,submitted_at,finished_at '
            'FROM creation_attempts WHERE id=%s AND user_id=%s',
            (attempt_id, user_id),
        )
        if not rows:
            return None
        row = rows[0]
        details = cls._replay_details(db, row) if (row['outcome'] == 'success' and row['ticket_id']) else None
        persisted = bool(details)
        if persisted:
            msg = f"Guardado confirmado en la base de datos (reporte #{details['ticket_id']})."
        elif row['outcome'] == 'processing':
            msg = 'El servidor sigue procesando esta solicitud.'
        elif row['outcome'] == 'failed':
            if row.get('outcome_reason') == 'stale_processing_timeout':
                msg = 'El intento anterior excedió el tiempo de procesamiento sin crear ticket; inicia uno nuevo.'
            else:
                msg = 'El intento falló y no creó ningún ticket en la base de datos.'
        elif row['outcome'] == 'abandoned':
            msg = 'La medición fue cancelada, expiró o se reemplazó antes de enviarse.'
        else:
            msg = 'La medición está iniciada, aún pendiente de envío.'
        return {
            'attempt_id': row['id'],
            'channel': row['channel'],
            'outcome': row['outcome'],
            'outcome_reason': row.get('outcome_reason'),
            'persisted_in_db': persisted,
            'browser_confirmed': row.get('client_confirmed_at') is not None,
            'ticket_id': details['ticket_id'] if details else None,
            'preparation_ms': row['preparation_ms'],
            'processing_ms': row['processing_ms'],
            'total_ms': row['total_ms'],
            'server_total_ms': row['total_ms'],
            'browser_roundtrip_ms': row.get('browser_roundtrip_ms'),
            'browser_total_ms': row.get('browser_total_ms'),
            'classification_status': details['classification_status'] if details else None,
            'priority_source': details['priority_source'] if details else None,
            'has_mixed_requests': details['has_mixed_requests'] if details else False,
            'request_kind': details['request_kind'] if details else None,
            'priority': details['priority'] if details else None,
            'status_message': msg,
        }


def measure_submission(channel):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if request.method != 'POST':
                return function(*args, **kwargs)
            if 'user_id' not in session:
                if channel == 'voice':
                    return jsonify(error='Sesión requerida para registrar reportes por voz.'), 401
                return redirect(url_for('login'))
            attempt_id = request.form.get('attempt_id')
            if channel == 'voice' and not attempt_id:
                try:
                    attempt_id = MeasurementService.start('voice', request.form.get('request_kind', 'incident'), request.form.get('origin_area_id'))
                except (ValueError, TypeError) as error:
                    return jsonify(error=str(error)), 400
            # Clientes anteriores siguen operando, pero sus tiempos no se inventan.
            if not attempt_id:
                return function(*args, **kwargs)
            client_metrics = {
                'pause_count': request.form.get('pause_count'),
                'paused_ms': request.form.get('paused_ms'),
                'client_prep_ms': request.form.get('client_prep_ms'),
            }
            try:
                row = MeasurementService.begin(attempt_id, channel, client_metrics=client_metrics)
            except MeasurementBusyError as error:
                if channel == 'voice':
                    return jsonify(error=str(error), already_processing=True, attempt_id=attempt_id), 409
                flash(str(error), 'warning')
                return redirect(url_for('create_ticket'))
            except (ValueError, TypeError) as error:
                if channel == 'voice':
                    return jsonify(error=str(error)), 409
                flash(str(error), 'warning')
                return redirect(url_for('create_ticket'))
            if row['outcome'] == 'success':
                if not row['ticket_id']:
                    if channel == 'voice':
                        return jsonify(error='El reporte de esta medición ya no existe.'), 409
                    flash('El reporte asociado a este intento ya no existe.', 'warning')
                    return redirect(url_for('create_ticket'))
                details = MeasurementService._replay_details(Database(), row)
                if not details:
                    if channel == 'voice':
                        return jsonify(error='El reporte de esta medición ya no existe.'), 409
                    flash('El reporte asociado a este intento ya no existe.', 'warning')
                    return redirect(url_for('create_ticket'))
                if channel == 'voice':
                    return jsonify(
                        mensaje='El reporte ya estaba confirmado en la base de datos; se recuperó sin duplicar.',
                        ticket_id=details['ticket_id'],
                        total_ms=row['total_ms'],
                        server_total_ms=row['total_ms'],
                        already_persisted=True,
                        persisted_in_db=True,
                        replayed=True,
                        classification_status=details['classification_status'],
                        priority_source=details['priority_source'],
                        has_mixed_requests=details['has_mixed_requests'],
                        request_kind=details['request_kind'],
                        priority=details['priority'],
                    ), 200
                flash(f"Este reporte ya estaba confirmado en la base de datos (#{details['ticket_id']}); no se creó un duplicado.", 'info')
                return redirect(url_for('view_ticket', ticket_id=details['ticket_id']))
            started = perf_counter()
            g.measurement_attempt_id = attempt_id
            g.measurement_started_perf = started
            g.measurement_finalized = False
            g.measurement_total_ms = None
            g.measurement_error_reason = None
            g.created_ticket_id = None
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                if not getattr(g, 'measurement_finalized', False):
                    MeasurementService.finish(
                        attempt_id,
                        perf_counter() - started,
                        reason=getattr(g, 'measurement_error_reason', None) or getattr(exc, 'error_code', type(exc).__name__),
                    )
                raise
            if getattr(g, 'created_ticket_id', None) and getattr(g, 'measurement_finalized', False):
                total = g.measurement_total_ms
            else:
                total = MeasurementService.finish(
                    attempt_id,
                    perf_counter() - started,
                    getattr(g, 'created_ticket_id', None),
                    reason=getattr(g, 'measurement_error_reason', None),
                )
            if getattr(g, 'created_ticket_id', None):
                if channel == 'manual':
                    flash(f'Registro manual guardado en servidor en {total/1000:.1f} s.', 'success')
                else:
                    response, status = result if isinstance(result, tuple) else (result, 200)
                    data = response.get_json()
                    data['total_ms'] = total
                    data['server_total_ms'] = total
                    data['persisted_in_db'] = True
                    return jsonify(data), status
            return result
        return wrapped
    return decorate
