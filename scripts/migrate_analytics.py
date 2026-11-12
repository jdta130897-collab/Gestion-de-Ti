"""Tablas aditivas para mediciones y notificaciones; no fabrica tiempos históricos."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.database import Database


def migrate():
    db = Database()
    if db.is_postgres:
        from scripts.migrate_postgres import migrate as migrate_postgres
        migrate_postgres()
        return
    db.execute_update('''CREATE TABLE IF NOT EXISTS creation_attempts (
        id CHAR(36) PRIMARY KEY, user_id INT NOT NULL, origin_area_id INT NOT NULL,
        channel ENUM('manual','voice') NOT NULL, request_kind ENUM('incident','request') NOT NULL,
        started_at DATETIME(6) NOT NULL, submitted_at DATETIME(6) NULL, finished_at DATETIME(6) NULL,
        outcome ENUM('started','processing','success','failed','abandoned') NOT NULL DEFAULT 'started',
        preparation_ms DOUBLE NULL, processing_ms DOUBLE NULL, total_ms DOUBLE NULL,
        ticket_id INT NULL, word_count INT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (origin_area_id) REFERENCES areas(id),
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE SET NULL,
        INDEX ix_attempt_scope(user_id, origin_area_id, started_at), INDEX ix_attempt_ticket(ticket_id)
    ) ENGINE=InnoDB''')
    db.execute_update('''CREATE TABLE IF NOT EXISTS notifications (
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, ticket_id INT NOT NULL,
        kind VARCHAR(30) NOT NULL, message VARCHAR(255) NOT NULL,
        created_at DATETIME(6) NOT NULL, read_at DATETIME(6) NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
        INDEX ix_notification_inbox(user_id, read_at, created_at)
    ) ENGINE=InnoDB''')
    print('Mediciones y notificaciones listas. Los tiempos previos permanecen sin medir.')
    from scripts.migrate_private_audio import migrate as migrate_audio
    migrate_audio()


if __name__ == '__main__':
    migrate()
