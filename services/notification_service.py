from config.database import Database
from flask import has_request_context, session
from utils.timezone import utc_now


class NotificationService:
    @staticmethod
    def emit(ticket_id, kind, message):
        db = Database()
        ticket = db.execute_query('SELECT * FROM tickets WHERE id=%s', (ticket_id,))[0]
        recipients = db.execute_query('''SELECT DISTINCT u.id FROM users u JOIN areas a ON a.id=u.area_id
            WHERE u.is_active=TRUE AND a.is_active=TRUE AND (
            u.role='super_admin' OR (u.role='manager' AND u.area_id=%s)
            OR u.id=%s OR u.id=%s OR (u.role='manager' AND u.area_id=%s))''',
            (ticket['destination_area_id'], ticket['created_by'], ticket['assigned_to'], ticket['origin_area_id']))
        actor = session.get('user_id') if has_request_context() else None
        now = utc_now()
        for user in recipients:
            if user['id'] == actor:
                continue
            db.execute_update('INSERT INTO notifications (user_id,ticket_id,kind,message,created_at) VALUES (%s,%s,%s,%s,%s)', (user['id'], ticket_id, kind, message[:255], now))
