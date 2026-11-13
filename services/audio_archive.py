"""Archivo privado en la base de datos; no crea URLs públicas ni usa el nombre del usuario."""
from hashlib import sha256
from pathlib import Path
import uuid
from config.database import Database
from services.participant_service import ParticipantService
from utils.release import get_evaluation_session_id, get_release_metadata
from utils.timezone import utc_now as _utc_naive


class AudioArchive:
    @staticmethod
    def save(path, user_id, attempt_id):
        db = Database()
        attempt = db.execute_query(
            'SELECT * FROM creation_attempts WHERE id=%s AND user_id=%s AND channel=%s AND outcome=%s',
            (attempt_id, user_id, 'voice', 'processing'),
        )
        if not attempt:
            raise ValueError('La grabación necesita un intento de voz válido del usuario.')
        data = Path(path).read_bytes()
        if not 0 < len(data) <= 3900000:
            raise ValueError('El audio debe contener datos y ocupar como máximo 3,9 MB.')
        extension = Path(path).suffix.lower()
        types = {'.webm': 'audio/webm', '.wav': 'audio/wav', '.mp3': 'audio/mpeg'}
        if extension not in types:
            raise ValueError('Formato de audio no permitido.')

        participant = ParticipantService.ensure_for_user(user_id)
        release = get_release_metadata()
        recording_id = str(uuid.uuid4())
        now = _utc_naive()
        db.execute_update(
            '''INSERT INTO voice_recordings
               (id,attempt_id,participant_id,user_id,software_version,build_commit,commit_dirty,
                evaluation_session_id,mime_type,byte_size,sha256,audio_data,consent_at,created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (
                recording_id,
                attempt_id,
                participant['id'],
                user_id,
                release['version'],
                release['commit'] or None,
                release['dirty'],
                get_evaluation_session_id(),
                types[extension],
                len(data),
                sha256(data).hexdigest(),
                data,
                now,
                now,
            ),
        )
        return recording_id

    @staticmethod
    def finish(recording_id, ticket_id=None, transcript=None, error_code=None, tx=None):
        sql = (
            'UPDATE voice_recordings SET ticket_id=%s,transcript=%s,outcome=%s,'
            'error_code=%s,completed_at=%s WHERE id=%s'
        )
        params = (
            ticket_id,
            transcript,
            'success' if ticket_id else 'failed',
            error_code,
            _utc_naive(),
            recording_id,
        )
        if tx is not None:
            return tx.execute(sql, params)
        return Database().execute_update(sql, params)
