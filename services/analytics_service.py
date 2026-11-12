from datetime import datetime, timedelta
from statistics import mean, median, stdev
from flask import session
from config.database import Database
from utils.permissions import is_super_admin


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
        kind = args.get('kind')
        if kind and kind not in ('request', 'incident'):
            raise ValueError('Tipo de solicitud no válido.')
        result['kind'] = kind
        return result

    @staticmethod
    def scope(alias):
        if is_super_admin():
            return '1=1', []
        if session['user_role'] == 'manager':
            return f'{alias}.origin_area_id=%s', [session['area_id']]
        column = 'user_id' if alias == 'm' else 'created_by'
        return f'{alias}.{column}=%s', [session['user_id']]

    @staticmethod
    def data(args):
        filters = AnalyticsService.filters(args)
        db = Database()
        db.execute_update("UPDATE creation_attempts SET outcome='abandoned',finished_at=UTC_TIMESTAMP(6) WHERE outcome='started' AND started_at < UTC_TIMESTAMP(6)-INTERVAL 2 HOUR")
        condition, params = AnalyticsService.scope('m')
        clauses = [condition]
        # Las fechas de la interfaz usan el horario de Lima (UTC-5).
        if filters.get('date_from'):
            clauses.append('m.started_at>=%s'); params.append(filters['date_from']+timedelta(hours=5))
        if filters.get('date_to'):
            clauses.append('m.started_at<%s'); params.append(filters['date_to']+timedelta(days=1,hours=5))
        if filters['kind']:
            clauses.append('m.request_kind=%s'); params.append(filters['kind'])
        rows = db.execute_query('''SELECT m.*,a.name AS area_name,p.code AS participant_code FROM creation_attempts m
            JOIN areas a ON a.id=m.origin_area_id LEFT JOIN research_participants p ON p.user_id=m.user_id
            WHERE ''' + ' AND '.join(clauses) + ' ORDER BY m.started_at', params)
        groups = {}
        for channel in ('voice', 'manual'):
            attempts = [r for r in rows if r['channel'] == channel]
            success = [r for r in attempts if r['outcome'] == 'success' and r['total_ms'] is not None]
            values = sorted(float(r['total_ms'])/1000 for r in success)
            completed = [r for r in attempts if r['outcome'] in ('success', 'failed')]
            groups[channel] = {
                'attempts': len(attempts), 'success': len(success),
                'failed': sum(r['outcome']=='failed' for r in attempts),
                'abandoned': sum(r['outcome']=='abandoned' for r in attempts),
                'pending': sum(r['outcome'] in ('started','processing') for r in attempts),
                'success_rate': len(success)/len(completed)*100 if completed else None,
                'mean_s': mean(values) if values else None, 'median_s': median(values) if values else None,
                'p90_s': float(__import__('numpy').percentile(values, 90)) if values else None,
                'min_s': min(values) if values else None, 'max_s': max(values) if values else None,
                'std_s': stdev(values) if len(values)>1 else None,
                'preparation_s': mean(float(r['preparation_ms'])/1000 for r in success) if success else None,
                'processing_s': mean(float(r['processing_ms'])/1000 for r in success) if success else None,
            }
        voice, manual = groups['voice'], groups['manual']
        reduction = (manual['mean_s']-voice['mean_s'])/manual['mean_s']*100 if voice['mean_s'] is not None and manual['mean_s'] else None
        daily = {}
        for row in rows:
            day = (row['started_at']-timedelta(hours=5)).strftime('%d/%m/%Y')
            daily.setdefault(day, {'voice': 0, 'manual': 0})
            if row['outcome'] == 'success':
                daily[day][row['channel']] += 1
        from controllers.ticket_controller import TicketController
        tickets = TicketController.get_all_tickets().get('data', [])
        tickets = [t for t in tickets if (not filters.get('date_from') or t['created_at'] >= filters['date_from']) and
                   (not filters.get('date_to') or t['created_at'] < filters['date_to']+timedelta(days=1)) and
                   (not filters['kind'] or t['request_kind']==filters['kind'])]
        measured_ids = {r['ticket_id'] for r in db.execute_query("SELECT ticket_id FROM creation_attempts WHERE outcome='success' AND ticket_id IS NOT NULL")}
        status = {key: sum(t['status']==key for t in tickets) for key in ('open','in_progress','resolved','closed')}
        priority = {key: sum(t['priority']==key for t in tickets) for key in ('low','medium','high','critical')}
        summary = {
            'updated_at': datetime.utcnow().isoformat()+'Z', 'channels': groups,
            'reduction_pct': reduction, 'measured_success': voice['success']+manual['success'],
            'unmeasured': sum(t['id'] not in measured_ids for t in tickets),
            'tickets_total': len(tickets), 'status': status, 'priority': priority,
            'daily': [{'day': k, **v} for k,v in daily.items()],
            'scope': 'Todas las áreas' if is_super_admin() else (session.get('area_name') if session['user_role']=='manager' else 'Tus solicitudes'),
            'methodology': 'Desde la primera interacción registrada por el servidor hasta la confirmación de creación. Incluye preparación, pausas, envío, transcripción y guardado. Solo los intentos exitosos con medición entran en los tiempos; tasa de éxito = éxitos / (éxitos + fallos). Fechas en horario de Lima. Comparación observacional: el tipo, la complejidad y las pausas pueden diferir; no demuestra causalidad.',
            'sample_note': 'Sin datos suficientes para comparar.' if reduction is None else ('Muestra pequeña: menos de 10 éxitos en uno de los canales.' if min(voice['success'], manual['success'])<10 else 'Interpreta los resultados según la complejidad de las solicitudes.'),
        }
        return summary, rows
