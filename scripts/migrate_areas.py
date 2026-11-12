"""Migración aditiva e idempotente del flujo de áreas. Conserva los registros existentes."""
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
    db.execute_update("""CREATE TABLE IF NOT EXISTS areas (
        id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(20) NOT NULL UNIQUE,
        name VARCHAR(100) NOT NULL UNIQUE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB""")
    db.execute_update("INSERT IGNORE INTO areas (code, name) VALUES ('TI', 'Tecnología de la información')")
    columns = {r['Field'] for r in db.execute_query('SHOW COLUMNS FROM users')}
    if 'area_id' not in columns:
        db.execute_update('ALTER TABLE users ADD area_id INT NULL, ADD CONSTRAINT fk_user_area FOREIGN KEY (area_id) REFERENCES areas(id)')
    role = next(r for r in db.execute_query('SHOW COLUMNS FROM users') if r['Field'] == 'role')
    if 'super_admin' not in role['Type']:
        db.execute_update("ALTER TABLE users MODIFY role ENUM('super_admin','admin','manager','technician','user') NOT NULL")
    ti = db.execute_query("SELECT id FROM areas WHERE code='TI'")[0]['id']
    db.execute_update('UPDATE users SET area_id=%s WHERE area_id IS NULL', (ti,))
    # Elevar únicamente la cuenta administrativa inicial; nunca cambiar su contraseña.
    if not db.execute_query("SELECT id FROM users WHERE role='super_admin'"):
        initial = db.execute_query("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1")
        if initial:
            db.execute_update("UPDATE users SET role='super_admin' WHERE id=%s", (initial[0]['id'],))
    columns = {r['Field'] for r in db.execute_query('SHOW COLUMNS FROM tickets')}
    definitions = {
        'origin_area_id': 'INT NULL REFERENCES areas(id)',
        'destination_area_id': 'INT NULL REFERENCES areas(id)',
        'request_kind': "ENUM('incident','request') NOT NULL DEFAULT 'incident'",
        'channel': "ENUM('manual','voice') NOT NULL DEFAULT 'manual'",
    }
    for field, definition in definitions.items():
        if field not in columns:
            db.execute_update(f'ALTER TABLE tickets ADD {field} {definition}')
    db.execute_update('UPDATE tickets t JOIN users u ON u.id=t.created_by SET t.origin_area_id=u.area_id WHERE t.origin_area_id IS NULL')
    db.execute_update('UPDATE tickets SET destination_area_id=%s WHERE destination_area_id IS NULL', (ti,))
    db.execute_update("UPDATE tickets t SET channel='voice' WHERE EXISTS (SELECT 1 FROM ticket_comments c WHERE c.ticket_id=t.id AND c.comment LIKE 'Creado desde transcrip%')")
    print('Migración de áreas completada; TI y registros existentes conservados.')
    from scripts.migrate_analytics import migrate as migrate_analytics
    migrate_analytics()


if __name__ == '__main__':
    migrate()
