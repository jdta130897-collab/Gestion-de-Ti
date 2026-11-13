from datetime import datetime, timedelta
from statistics import mean, median, stdev
import numpy as np
from flask import session
from config.database import Database
from services.measurement_service import MeasurementService
from utils.permissions import is_super_admin, is_ti
from utils.release import POLICY_VERSION, PROMPT_VERSION, get_release_metadata
from utils.timezone import (
    TIMEZONE_NAME,
    UTC_OFFSET_LABEL,
    lima_day_bounds_to_utc,
    to_lima,
    utc_iso,
    utc_now,
)


SCOPE_OPTIONS = ('auto', 'personal', 'area', 'global')


class AnalyticsService:
    @staticmethod
    def filters(args):
        result = {}
        for key in ('date_from', 'date_to'):
            value = args.get(key)
            if value:
                try:
                    result[key] = datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    raise ValueError('Las fechas deben tener formato año-mes-día.')
        if result.get('date_from') and result.get('date_to') and result['date_from'] > result['date_to']:
            raise ValueError('La fecha inicial no puede ser posterior a la final.')
        kind = args.get('kind') or None
        if kind and kind not in ('request', 'incident'):
            raise ValueError('Tipo de solicitud no válido.')
        result['kind'] = kind

        scope_req = (args.get('scope') or 'auto').strip().lower()
        if scope_req not in SCOPE_OPTIONS:
            raise ValueError('Alcance de consulta no válido.')
        if scope_req == 'global' and not is_super_admin():
            raise ValueError('Solo el superadministrador puede consultar el alcance global.')
        if scope_req == 'area' and not (is_super_admin() or session.get('user_role') == 'manager'):
            raise ValueError('El alcance de área requiere perfil de encargado o superadministrador.')
        result['scope'] = scope_req

        eval_session = (args.get('evaluation_session_id') or '').strip()
        if len(eval_session) > 64:
            raise ValueError('El identificador de sesión de evaluación es demasiado largo.')
        result['evaluation_session_id'] = eval_session or None
        return result

    @staticmethod
    def scope_metadata(requested_scope='auto'):
        role = session.get('user_role') or 'user'
        area_name = session.get('area_name') or 'Tu área'
        available = [{'value': 'auto', 'label': 'Alcance correspondiente al rol'}, {'value': 'personal', 'label': 'Solo mis solicitudes e intentos (personal)'}]
        if role == 'manager':
            available.append({'value': 'area', 'label': f'Operativo TI ({area_name})' if is_ti() else f'Área ({area_name})'})
        elif is_super_admin():
            available.append({'value': 'area', 'label': f'Área ({area_name})'})
            available.append({'value': 'global', 'label': 'Global (todas las áreas)'})

        if requested_scope == 'personal':
            return 'personal', 'Personal (tus solicitudes e intentos)', available
        if is_super_admin() and requested_scope in ('auto', 'global'):
            return 'global', 'Global (todas las áreas)', available
        if role == 'manager' or (is_super_admin() and requested_scope == 'area'):
            if is_ti():
                return 'operational_ti', f'Operativo TI (hacia TI y {area_name})', available
            return 'area', f'Área ({area_name})', available
        if is_ti():
            return 'personal_assigned', 'Personal y atención asignada en TI', available
        return 'personal', 'Personal (tus solicitudes)', available

    @staticmethod
    def ticket_scope(alias='t', requested_scope='auto'):
        if requested_scope == 'personal':
            return f'{alias}.created_by=%s', [session['user_id']]
        if is_super_admin() and requested_scope in ('auto', 'global'):
            return '1=1', []
        area_id = session.get('area_id')
        if session.get('user_role') == 'manager' or (is_super_admin() and requested_scope == 'area'):
            return f'({alias}.origin_area_id=%s OR {alias}.destination_area_id=%s)', [area_id, area_id]
        return f'({alias}.created_by=%s OR ({alias}.destination_area_id=%s AND {alias}.assigned_to=%s))', [
            session['user_id'],
            area_id,
            session['user_id'],
        ]

    @staticmethod
    def measurement_scope(alias='m', ticket_alias='t', requested_scope='auto'):
        if requested_scope == 'personal':
            return f'{alias}.user_id=%s', [session['user_id']]
        if is_super_admin() and requested_scope in ('auto', 'global'):
            return '1=1', []
        area_id = session.get('area_id')
        if session.get('user_role') == 'manager' or (is_super_admin() and requested_scope == 'area'):
            if is_ti():
                return f'({alias}.origin_area_id=%s OR {ticket_alias}.destination_area_id=%s)', [area_id, area_id]
            return f'{alias}.origin_area_id=%s', [area_id]
        return f'{alias}.user_id=%s', [session['user_id']]

    @staticmethod
    def scope(alias='m', requested_scope='auto'):
        if alias == 't':
            return AnalyticsService.ticket_scope('t', requested_scope=requested_scope)
        return AnalyticsService.measurement_scope(alias, 't', requested_scope=requested_scope)

    @staticmethod
    def _channel_stats(attempts):
        success = [r for r in attempts if r['outcome'] == 'success' and r['total_ms'] is not None]
        failed = [r for r in attempts if r['outcome'] == 'failed']
        abandoned = [r for r in attempts if r['outcome'] == 'abandoned']
        pending = [r for r in attempts if r['outcome'] in ('started', 'processing')]
        values = sorted(float(r['total_ms']) / 1000 for r in success)
        completed = len(success) + len(failed)
        total_attempts = len(attempts)

        paused_vals = [float(r['paused_ms']) / 1000 for r in success if r.get('paused_ms') is not None]
        pause_counts = [int(r['pause_count']) for r in success if r.get('pause_count') is not None]
        browser_total_vals = [float(r['browser_total_ms']) / 1000 for r in success if r.get('browser_total_ms') is not None]
        browser_rt_vals = [float(r['browser_roundtrip_ms']) / 1000 for r in success if r.get('browser_roundtrip_ms') is not None]
        browser_confirmed = sum(r.get('client_confirmed_at') is not None for r in success)
        browser_recovered = sum(r.get('outcome_reason') == 'recovered_after_lost_response' for r in success)

        return {
            'attempts': total_attempts,
            'success': len(success),
            'failed': len(failed),
            'stale_processing_failed': sum(r.get('outcome_reason') == 'stale_processing_timeout' for r in failed),
            'abandoned': len(abandoned),
            'pending': len(pending),
            'pending_started': sum(r['outcome'] == 'started' for r in pending),
            'pending_processing': sum(r['outcome'] == 'processing' for r in pending),
            'success_rate': (len(success) / completed * 100) if completed else None,
            'completion_rate': (len(success) / total_attempts * 100) if total_attempts else None,
            'mean_s': mean(values) if values else None,
            'server_total_mean_s': mean(values) if values else None,
            'median_s': median(values) if values else None,
            'p90_s': float(np.percentile(values, 90)) if values else None,
            'min_s': min(values) if values else None,
            'max_s': max(values) if values else None,
            'std_s': stdev(values) if len(values) > 1 else None,
            'preparation_s': mean(float(r['preparation_ms']) / 1000 for r in success if r.get('preparation_ms') is not None) if any(r.get('preparation_ms') is not None for r in success) else None,
            'processing_s': mean(float(r['processing_ms']) / 1000 for r in success if r.get('processing_ms') is not None) if any(r.get('processing_ms') is not None for r in success) else None,
            'paused_samples': len(paused_vals),
            'paused_s': mean(paused_vals) if paused_vals else None,
            'pause_count_mean': mean(pause_counts) if pause_counts else None,
            'browser_confirmed': browser_confirmed,
            'browser_unconfirmed': len(success) - browser_confirmed,
            'browser_recovered': browser_recovered,
            'browser_mean_s': mean(browser_total_vals) if browser_total_vals else None,
            'browser_roundtrip_s': mean(browser_rt_vals) if browser_rt_vals else None,
        }

    @staticmethod
    def data(args):
        filters = AnalyticsService.filters(args)
        db = Database()
        MeasurementService.sweep_stale(db)

        utc_start, utc_end_exclusive = lima_day_bounds_to_utc(filters.get('date_from'), filters.get('date_to'))
        requested_scope = filters['scope']
        scope_level, scope_label, available_scopes = AnalyticsService.scope_metadata(requested_scope)

        condition, params = AnalyticsService.measurement_scope('m', 't', requested_scope=requested_scope)
        clauses = [condition]
        if utc_start is not None:
            clauses.append('m.started_at>=%s')
            params.append(utc_start)
        if utc_end_exclusive is not None:
            clauses.append('m.started_at<%s')
            params.append(utc_end_exclusive)
        if filters['kind']:
            clauses.append('m.request_kind=%s')
            params.append(filters['kind'])
        if filters['evaluation_session_id']:
            clauses.append('m.evaluation_session_id=%s')
            params.append(filters['evaluation_session_id'])

        rows = db.execute_query(
            '''SELECT m.*, a.name AS area_name, p.code AS participant_code,
                      t.priority AS ticket_priority, t.status AS ticket_status,
                      cs.classification_status, cs.priority_source, cs.policy_version, cs.prompt_version
               FROM creation_attempts m
               JOIN areas a ON a.id=m.origin_area_id
               LEFT JOIN research_participants p ON p.user_id=m.user_id
               LEFT JOIN tickets t ON t.id=m.ticket_id
               LEFT JOIN classification_snapshots cs ON cs.attempt_id=m.id
               WHERE '''
            + ' AND '.join(clauses)
            + ' ORDER BY m.started_at',
            params,
        )

        groups = {
            channel: AnalyticsService._channel_stats([r for r in rows if r['channel'] == channel])
            for channel in ('voice', 'manual')
        }
        voice, manual = groups['voice'], groups['manual']
        reduction = (
            (manual['mean_s'] - voice['mean_s']) / manual['mean_s'] * 100
            if voice['mean_s'] is not None and manual['mean_s']
            else None
        )
        browser_reduction = (
            (manual['browser_mean_s'] - voice['browser_mean_s']) / manual['browser_mean_s'] * 100
            if voice['browser_mean_s'] is not None and manual['browser_mean_s']
            else None
        )

        daily = {}
        for row in rows:
            day = to_lima(row['started_at']).strftime('%d/%m/%Y')
            daily.setdefault(day, {'voice': 0, 'manual': 0})
            if row['outcome'] == 'success':
                daily[day][row['channel']] += 1

        from controllers.ticket_controller import TicketController
        all_visible_tickets = TicketController.get_all_tickets().get('data', [])
        tickets = [
            t for t in all_visible_tickets
            if (utc_start is None or (t.get('created_at') and t['created_at'] >= utc_start))
            and (utc_end_exclusive is None or (t.get('created_at') and t['created_at'] < utc_end_exclusive))
            and (not filters['kind'] or t.get('request_kind') == filters['kind'])
            and (not filters['evaluation_session_id'] or t.get('evaluation_session_id') == filters['evaluation_session_id'])
            and (requested_scope != 'personal' or t.get('created_by') == session.get('user_id'))
        ]

        measured_ids = {
            r['ticket_id']
            for r in db.execute_query("SELECT ticket_id FROM creation_attempts WHERE outcome='success' AND ticket_id IS NOT NULL")
        }
        status = {key: sum(t['status'] == key for t in tickets) for key in ('open', 'in_progress', 'resolved', 'closed')}
        priority = {key: sum(t['priority'] == key for t in tickets) for key in ('low', 'medium', 'high', 'critical')}

        uid = session.get('user_id')
        personal_tickets = [
            t for t in all_visible_tickets
            if t.get('created_by') == uid
            and (utc_start is None or (t.get('created_at') and t['created_at'] >= utc_start))
            and (utc_end_exclusive is None or (t.get('created_at') and t['created_at'] < utc_end_exclusive))
            and (not filters['kind'] or t.get('request_kind') == filters['kind'])
            and (not filters['evaluation_session_id'] or t.get('evaluation_session_id') == filters['evaluation_session_id'])
        ]
        personal_attempts = [r for r in rows if r.get('user_id') == uid] if scope_level in ('personal', 'personal_assigned') else db.execute_query(
            'SELECT m.outcome, m.total_ms FROM creation_attempts m WHERE m.user_id=%s'
            + (' AND m.started_at>=%s' if utc_start is not None else '')
            + (' AND m.started_at<%s' if utc_end_exclusive is not None else '')
            + (' AND m.request_kind=%s' if filters['kind'] else '')
            + (' AND m.evaluation_session_id=%s' if filters['evaluation_session_id'] else ''),
            [
                uid,
                *([utc_start] if utc_start is not None else []),
                *([utc_end_exclusive] if utc_end_exclusive is not None else []),
                *([filters['kind']] if filters['kind'] else []),
                *([filters['evaluation_session_id']] if filters['evaluation_session_id'] else []),
            ],
        )

        created_by_me = sum(t.get('created_by') == uid for t in tickets)
        assigned_to_me = sum(t.get('assigned_to') == uid for t in tickets)
        unassigned_open = sum(t.get('status') in ('open', 'in_progress') and not t.get('assigned_to') for t in tickets)
        measured_tickets = sum(t['id'] in measured_ids for t in tickets)
        unmeasured_tickets = len(tickets) - measured_tickets

        denominators = {
            'attempts_total': {
                'voice': voice['attempts'],
                'manual': manual['attempts'],
                'formula': 'success + failed + abandoned + pending',
            },
            'success_rate': {
                'voice_denominator': voice['success'] + voice['failed'],
                'manual_denominator': manual['success'] + manual['failed'],
                'formula': 'success / (success + failed) * 100 (excluye abandonados y pendientes)',
            },
            'completion_rate': {
                'voice_denominator': voice['attempts'],
                'manual_denominator': manual['attempts'],
                'formula': 'success / attempts * 100 (incluye abandonados y pendientes en el total)',
            },
            'server_timings': {
                'voice_n': voice['success'],
                'manual_n': manual['success'],
                'formula': "outcome == 'success' AND total_ms IS NOT NULL (hasta confirmación en BD, antes de respuesta HTTP)",
            },
            'browser_timings': {
                'voice_n': voice['browser_confirmed'],
                'manual_n': manual['browser_confirmed'],
                'formula': "outcome == 'success' AND browser_total_ms IS NOT NULL (hasta confirmación visual en navegador)",
            },
            'operational_tickets': {
                'total': len(tickets),
                'measured': measured_tickets,
                'unmeasured': unmeasured_tickets,
                'formula': 'Todos los tickets autorizados en el alcance y período (con y sin medición experimental)',
            },
        }

        timing_definitions = {
            'preparation_ms': 'Desde started_at (primera interacción manual o inicio de grabación tras permiso de micrófono) hasta submitted_at (recepción del envío en servidor). Incluye pausas de escritura/grabación.',
            'paused_ms': 'Pausas detectadas en el cliente (pestaña oculta o inactividad >= 5 s durante preparación). Ya forman parte de preparation_ms.',
            'processing_ms': 'Duración dentro del servidor desde begin hasta fin del flujo (en voz incluye archivo privado, transcripción, clasificación y guardado transaccional).',
            'total_ms': 'Duración total en servidor (finished_at - started_at hasta confirmar la transacción en BD, previa a la entrega HTTP al navegador). No equivale a confirmación visual.',
            'browser_roundtrip_ms': 'Duración percibida por el navegador desde el envío hasta recibir y renderizar la confirmación visible (/api/measurements/<id>/confirm).',
            'browser_total_ms': 'Duración total percibida en el navegador desde inicio de interacción hasta la confirmación visible en pantalla.',
        }

        operational = {
            'tickets_total': len(tickets),
            'measured_tickets': measured_tickets,
            'unmeasured': unmeasured_tickets,
            'status': status,
            'priority': priority,
            'open_active': status['open'] + status['in_progress'],
            'resolved_closed': status['resolved'] + status['closed'],
            'created_by_me': created_by_me,
            'assigned_to_me': assigned_to_me,
            'unassigned_open': unassigned_open,
            'scope_level': scope_level,
            'scope_label': scope_label,
            'timezone': f'{TIMEZONE_NAME} ({UTC_OFFSET_LABEL})',
        }

        research = {
            'channels': groups,
            'reduction_pct': reduction,
            'browser_reduction_pct': browser_reduction,
            'measured_success': voice['success'] + manual['success'],
            'total_attempts': voice['attempts'] + manual['attempts'],
            'denominators': denominators,
            'timing_definitions': timing_definitions,
            'evaluation_session_id': filters['evaluation_session_id'],
            'scope_level': scope_level,
            'scope_label': scope_label,
        }

        scope_comparison = {
            'active': {
                'scope_level': scope_level,
                'scope_label': scope_label,
                'tickets_total': len(tickets),
                'attempts_total': voice['attempts'] + manual['attempts'],
                'measured_success': voice['success'] + manual['success'],
            },
            'personal': {
                'scope_level': 'personal',
                'scope_label': 'Tus datos personales (propios)',
                'tickets_total': len(personal_tickets),
                'tickets_open': sum(t.get('status') in ('open', 'in_progress') for t in personal_tickets),
                'attempts_total': len(personal_attempts),
                'measured_success': sum(a.get('outcome') == 'success' and a.get('total_ms') is not None for a in personal_attempts),
            },
        }

        sample_note = (
            'Sin datos suficientes para comparar.'
            if reduction is None
            else (
                'Muestra pequeña: menos de 10 éxitos en uno de los canales.'
                if min(voice['success'], manual['success']) < 10
                else 'Interpreta los resultados según la complejidad de las solicitudes.'
            )
        )

        methodology = (
            'Duración en servidor: desde el inicio de interacción registrado en servidor (started_at; en voz solo tras permiso de micrófono) '
            'hasta el guardado transaccional confirmado en BD (finished_at, previo a la entrega HTTP al navegador). '
            'La confirmación visible en navegador (browser_total_ms) se mide por separado cuando el cliente recibe y muestra la respuesta. '
            'Las pausas e inactividad forman parte de preparation_ms y se desglosan con paused_ms. '
            'Solo los intentos con outcome=success y total_ms no nulo entran en estadísticos de tiempo; '
            'tasa de éxito = éxitos / (éxitos + fallos); tasa de finalización = éxitos / intentos totales. '
            'Filtros diarios unificados en horario de Lima (UTC-5) sobre almacenamiento interno UTC (tickets históricos pre-Etapa 4 se conservan intactos). '
            'Comparación observacional: no demuestra causalidad.'
        )

        summary = {
            'updated_at': utc_iso(utc_now()),
            'channels': groups,
            'reduction_pct': reduction,
            'browser_reduction_pct': browser_reduction,
            'measured_success': voice['success'] + manual['success'],
            'unmeasured': unmeasured_tickets,
            'tickets_total': len(tickets),
            'status': status,
            'priority': priority,
            'daily': [{'day': k, **v} for k, v in daily.items()],
            'scope': scope_label,
            'scope_level': scope_level,
            'available_scopes': available_scopes,
            'scope_comparison': scope_comparison,
            'operational': operational,
            'research': research,
            'denominators': denominators,
            'timing_definitions': timing_definitions,
            'filters_applied': {
                'date_from': args.get('date_from') or None,
                'date_to': args.get('date_to') or None,
                'utc_start': utc_iso(utc_start),
                'utc_end_exclusive': utc_iso(utc_end_exclusive),
                'kind': filters['kind'],
                'scope': requested_scope,
                'evaluation_session_id': filters['evaluation_session_id'],
            },
            'methodology': methodology,
            'sample_note': sample_note,
        }
        return summary, rows

    @staticmethod
    def reproducible_bundle(args):
        summary, rows = AnalyticsService.data(args)
        release = get_release_metadata()
        exported_rows = []
        for row in rows:
            exported_rows.append({
                'attempt_id': row['id'],
                'ticket_id': row['ticket_id'],
                'participant_code': row.get('participant_code'),
                'area_name': row.get('area_name'),
                'channel': row['channel'],
                'request_kind': row['request_kind'],
                'outcome': row['outcome'],
                'outcome_reason': row.get('outcome_reason'),
                'started_at_utc': utc_iso(row.get('started_at')),
                'started_at_lima': to_lima(row['started_at']).isoformat() if row.get('started_at') else None,
                'submitted_at_utc': utc_iso(row.get('submitted_at')),
                'finished_at_utc': utc_iso(row.get('finished_at')),
                'client_confirmed_at_utc': utc_iso(row.get('client_confirmed_at')),
                'preparation_ms': row.get('preparation_ms'),
                'paused_ms': row.get('paused_ms'),
                'pause_count': row.get('pause_count'),
                'client_prep_ms': row.get('client_prep_ms'),
                'processing_ms': row.get('processing_ms'),
                'server_total_ms': row.get('total_ms'),
                'browser_roundtrip_ms': row.get('browser_roundtrip_ms'),
                'browser_total_ms': row.get('browser_total_ms'),
                'word_count': row.get('word_count'),
                'ticket_priority': row.get('ticket_priority'),
                'ticket_status': row.get('ticket_status'),
                'classification_status': row.get('classification_status'),
                'priority_source': row.get('priority_source'),
                'policy_version': row.get('policy_version'),
                'prompt_version': row.get('prompt_version'),
                'software_version': row.get('software_version'),
                'build_commit': row.get('build_commit'),
                'commit_dirty': row.get('commit_dirty'),
                'evaluation_session_id': row.get('evaluation_session_id'),
            })

        return {
            'schema_version': 'ingeniare-analytics-bundle/1.0',
            'generated_at_utc': utc_iso(utc_now()),
            'timezone': TIMEZONE_NAME,
            'utc_offset': UTC_OFFSET_LABEL,
            'software_release': {
                **release,
                'policy_version': POLICY_VERSION,
                'prompt_version': PROMPT_VERSION,
            },
            'active_filters': summary['filters_applied'],
            'selection_rules': {
                'scope_level': summary['scope_level'],
                'scope_label': summary['scope'],
                'started_expiry_seconds': 7200,
                'processing_stale_seconds': 600,
                'included_in_timings': "outcome == 'success' and server_total_ms is not None",
                'included_in_browser_timings': "outcome == 'success' and browser_total_ms is not None",
                'excluded_from_success_rate': ['started', 'processing', 'abandoned'],
                'historical_preservation': 'Registros previos a Etapa 4 no fueron reescritos retrospectivamente.',
            },
            'formulas': summary['denominators'],
            'timing_definitions': summary['timing_definitions'],
            'scope_comparison': summary['scope_comparison'],
            'operational': summary['operational'],
            'research': summary['research'],
            'attempts': exported_rows,
        }
