"""Archivo privado en la base de datos; no crea URLs públicas ni usa el nombre del usuario."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import uuid
from config.database import Database
from utils.release import SOFTWARE_VERSION, BUILD_COMMIT


class AudioArchive:
    @staticmethod
    def save(path,user_id,attempt_id):
        db=Database()
        attempt=db.execute_query('SELECT * FROM creation_attempts WHERE id=%s AND user_id=%s AND channel=%s AND outcome=%s',
            (attempt_id,user_id,'voice','processing'))
        if not attempt:
            raise ValueError('La grabación necesita un intento de voz válido del usuario.')
        data=Path(path).read_bytes()
        if not 0<len(data)<=3900000:
            raise ValueError('El audio debe contener datos y ocupar como máximo 3,9 MB.')
        extension=Path(path).suffix.lower()
        types={'.webm':'audio/webm','.wav':'audio/wav','.mp3':'audio/mpeg'}
        if extension not in types:
            raise ValueError('Formato de audio no permitido.')
        # Upsert atómico para que dos pestañas no generen dos códigos para una persona.
        participant_id=str(uuid.uuid4());code='P-'+uuid.uuid4().hex[:16].upper()
        if db.is_postgres:
            db.execute_update('INSERT INTO research_participants (id,user_id,code,created_at) VALUES (%s,%s,%s,%s) ON CONFLICT (user_id) DO NOTHING',
                (participant_id,user_id,code,datetime.utcnow()))
        else:
            db.execute_update('INSERT IGNORE INTO research_participants (id,user_id,code,created_at) VALUES (%s,%s,%s,%s)',
                (participant_id,user_id,code,datetime.utcnow()))
        participant_id=db.execute_query('SELECT id FROM research_participants WHERE user_id=%s',(user_id,))[0]['id']
        recording_id=str(uuid.uuid4());now=datetime.utcnow()
        db.execute_update('''INSERT INTO voice_recordings
            (id,attempt_id,participant_id,user_id,software_version,build_commit,mime_type,byte_size,sha256,audio_data,consent_at,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (recording_id,attempt_id,participant_id,user_id,SOFTWARE_VERSION,BUILD_COMMIT or None,types[extension],len(data),sha256(data).hexdigest(),data,now,now))
        return recording_id

    @staticmethod
    def finish(recording_id,ticket_id=None,transcript=None,error_code=None):
        Database().execute_update('''UPDATE voice_recordings SET ticket_id=%s,transcript=%s,outcome=%s,error_code=%s,completed_at=%s WHERE id=%s''',
            (ticket_id,transcript,'success' if ticket_id else 'failed',error_code,datetime.utcnow(),recording_id))
