"""Prepara bloqueos y unicidad; no convierte roles históricos automáticamente."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config.database import Database

def migrate():
 db=Database()
 if db.is_postgres:
  from scripts.migrate_postgres import migrate as pg
  return pg()
 columns={r['Field'] for r in db.execute_query('SHOW COLUMNS FROM tickets')}
 if 'classification_locked' not in columns:
  db.execute_update('ALTER TABLE tickets ADD classification_locked BOOLEAN NOT NULL DEFAULT FALSE')
 db.execute_update("UPDATE tickets SET classification_locked=TRUE WHERE classification_locked=FALSE AND (assigned_to IS NOT NULL OR status IN ('resolved','closed'))")
 db.execute_update('DROP TRIGGER IF EXISTS ticket_workflow_guard')
 db.execute_update('''CREATE TRIGGER ticket_workflow_guard BEFORE UPDATE ON tickets FOR EACH ROW BEGIN
 IF OLD.status IN ('resolved','closed') THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Un ticket resuelto o cerrado no puede editarse'; END IF;
 IF (OLD.classification_locked OR OLD.assigned_to IS NOT NULL) AND (NOT (NEW.priority <=> OLD.priority) OR NOT (NEW.request_kind <=> OLD.request_kind)) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La clasificación está bloqueada desde la primera asignación'; END IF;
 SET NEW.classification_locked = OLD.classification_locked OR NEW.assigned_to IS NOT NULL OR NEW.status IN ('resolved','closed'); END''')
 duplicates=db.execute_query("SELECT area_id FROM users WHERE role='manager' AND is_active=TRUE GROUP BY area_id HAVING COUNT(*)>1")
 if duplicates:raise ValueError('Hay áreas con varios encargados. Define el encargado antes de continuar; no se convertirán roles automáticamente.')
 columns={r['Field'] for r in db.execute_query('SHOW COLUMNS FROM users')}
 if 'active_manager_area' not in columns:
  db.execute_update("ALTER TABLE users ADD active_manager_area INT GENERATED ALWAYS AS (CASE WHEN role='manager' AND is_active=TRUE THEN area_id ELSE NULL END) STORED, ADD UNIQUE INDEX one_active_manager_per_area(active_manager_area)")
 print('Política de tickets preparada.')
if __name__=='__main__':migrate()
