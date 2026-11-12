"""Migración aditiva del archivo privado; nunca asigna versiones a datos antiguos."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config.database import Database


def migrate():
    db=Database()
    if db.is_postgres:
        from scripts.migrate_postgres import migrate as migrate_pg
        migrate_pg()
        return
    columns={r['Field'] for r in db.execute_query('SHOW COLUMNS FROM creation_attempts')}
    for field,size in (('software_version',30),('build_commit',64)):
        if field not in columns:
            db.execute_update(f'ALTER TABLE creation_attempts ADD {field} VARCHAR({size}) NULL')
    db.execute_update('''CREATE TABLE IF NOT EXISTS research_participants (
        id CHAR(36) PRIMARY KEY, user_id INT NOT NULL UNIQUE, code VARCHAR(30) NOT NULL UNIQUE,
        created_at DATETIME(6) NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB''')
    db.execute_update('''CREATE TABLE IF NOT EXISTS voice_recordings (
        id CHAR(36) PRIMARY KEY, attempt_id CHAR(36) NOT NULL UNIQUE,
        participant_id CHAR(36) NOT NULL, user_id INT NOT NULL, ticket_id INT NULL,
        software_version VARCHAR(30) NOT NULL, build_commit VARCHAR(64),
        mime_type VARCHAR(50) NOT NULL, byte_size INT NOT NULL, sha256 CHAR(64) NOT NULL,
        audio_data LONGBLOB NOT NULL, transcript TEXT,
        outcome VARCHAR(20) NOT NULL DEFAULT 'processing', error_code VARCHAR(100),
        consent_at DATETIME(6) NOT NULL, created_at DATETIME(6) NOT NULL, completed_at DATETIME(6),
        FOREIGN KEY (attempt_id) REFERENCES creation_attempts(id) ON DELETE CASCADE,
        FOREIGN KEY (participant_id) REFERENCES research_participants(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE SET NULL,
        INDEX ix_recordings_owner(user_id,created_at), INDEX ix_recordings_ticket(ticket_id)
    ) ENGINE=InnoDB''')
    from scripts.migrate_ticket_workflow import migrate as workflow
    workflow()
    print('Archivo privado de audios preparado; registros antiguos sin alterar.')


if __name__=='__main__':migrate()
