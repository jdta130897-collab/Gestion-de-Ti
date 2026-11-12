ALTER TABLE tickets ADD COLUMN IF NOT EXISTS classification_locked BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE tickets SET classification_locked=TRUE WHERE classification_locked=FALSE AND (assigned_to IS NOT NULL OR status IN ('resolved','closed'));
CREATE OR REPLACE FUNCTION enforce_ticket_workflow() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status IN ('resolved','closed') THEN
  RAISE EXCEPTION 'Un ticket resuelto o cerrado no puede editarse';
 END IF;
 IF (OLD.classification_locked OR OLD.assigned_to IS NOT NULL) AND
    (NEW.priority IS DISTINCT FROM OLD.priority OR NEW.request_kind IS DISTINCT FROM OLD.request_kind) THEN
  RAISE EXCEPTION 'La prioridad y el tipo están bloqueados desde la primera asignación';
 END IF;
 NEW.classification_locked := OLD.classification_locked OR NEW.assigned_to IS NOT NULL OR NEW.status IN ('resolved','closed');
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS ticket_workflow_guard ON tickets;
CREATE TRIGGER ticket_workflow_guard BEFORE UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION enforce_ticket_workflow();
-- No convierte roles históricos ni decide arbitrariamente quién es encargado.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_manager_per_area ON users(area_id) WHERE role='manager' AND is_active=TRUE;
