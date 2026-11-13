"""Gestión idempotente de seudónimos de participantes en manual y voz."""
import uuid
from config.database import Database
from utils.timezone import utc_now as _utc_naive


class ParticipantService:
    @staticmethod
    def ensure_for_user(user_id, tx=None):
        """Asegura un código de participante único para cualquier usuario (manual o voz)."""
        if not user_id:
            raise ValueError('Se requiere user_id para asignar código de participante.')
        db = Database()
        participant_id = str(uuid.uuid4())
        code = 'P-' + uuid.uuid4().hex[:16].upper()
        now = _utc_naive()

        insert_pg = (
            'INSERT INTO research_participants (id,user_id,code,created_at) '
            'VALUES (%s,%s,%s,%s) ON CONFLICT (user_id) DO NOTHING'
        )
        insert_mysql = (
            'INSERT IGNORE INTO research_participants (id,user_id,code,created_at) '
            'VALUES (%s,%s,%s,%s)'
        )
        select_sql = 'SELECT id,code FROM research_participants WHERE user_id=%s'
        sql = insert_pg if db.is_postgres else insert_mysql

        if tx is not None:
            tx.execute(sql, (participant_id, user_id, code, now))
            rows = tx.query(select_sql, (user_id,))
        else:
            db.execute_update(sql, (participant_id, user_id, code, now))
            rows = db.execute_query(select_sql, (user_id,))
        return rows[0]
