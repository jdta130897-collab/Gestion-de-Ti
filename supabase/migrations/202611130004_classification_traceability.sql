-- Migración aditiva para trazabilidad inmutable de clasificación inicial,
-- cambios humanos posteriores e idempotencia por attempt_id.
-- Conserva íntegramente los registros existentes sin completar retrospectivamente datos históricos.

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS attempt_id CHAR(36) REFERENCES creation_attempts(id) ON DELETE SET NULL;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS evaluation_session_id VARCHAR(64);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tickets_attempt_id ON tickets(attempt_id) WHERE attempt_id IS NOT NULL;

ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS commit_dirty BOOLEAN;
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS evaluation_session_id VARCHAR(64);

ALTER TABLE voice_recordings ADD COLUMN IF NOT EXISTS commit_dirty BOOLEAN;
ALTER TABLE voice_recordings ADD COLUMN IF NOT EXISTS evaluation_session_id VARCHAR(64);

CREATE TABLE IF NOT EXISTS classification_snapshots (
 id CHAR(36) PRIMARY KEY,
 attempt_id CHAR(36) REFERENCES creation_attempts(id) ON DELETE SET NULL,
 ticket_id INTEGER REFERENCES tickets(id) ON DELETE SET NULL,
 recording_id CHAR(36) REFERENCES voice_recordings(id) ON DELETE SET NULL,
 user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
 participant_id CHAR(36) REFERENCES research_participants(id) ON DELETE SET NULL,
 participant_code VARCHAR(30),
 evaluation_session_id VARCHAR(64),
 channel VARCHAR(10) NOT NULL CHECK (channel IN ('manual','voice')),
 source_mode VARCHAR(30) NOT NULL,
 transcript TEXT,
 raw_classifier_json TEXT,
 validated_payload_json TEXT,
 initial_request_kind VARCHAR(20),
 initial_impact VARCHAR(20),
 initial_urgency VARCHAR(20),
 initial_category VARCHAR(100),
 initial_reason TEXT,
 initial_priority VARCHAR(20),
 classification_status VARCHAR(30),
 priority_source VARCHAR(30),
 is_provisional BOOLEAN NOT NULL DEFAULT FALSE,
 has_mixed_requests BOOLEAN,
 in_scope BOOLEAN,
 scope_reason VARCHAR(40),
 classifier_model VARCHAR(100),
 classifier_config_json TEXT,
 prompt_version VARCHAR(40),
 policy_version VARCHAR(40) NOT NULL,
 software_version VARCHAR(30) NOT NULL,
 build_commit VARCHAR(64),
 commit_dirty BOOLEAN,
 error_code VARCHAR(100),
 created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_snapshot_attempt ON classification_snapshots(attempt_id) WHERE attempt_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_snapshot_ticket ON classification_snapshots(ticket_id);
CREATE INDEX IF NOT EXISTS ix_snapshot_participant ON classification_snapshots(participant_id, created_at);

CREATE OR REPLACE FUNCTION enforce_classification_snapshot_immutability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (OLD.attempt_id IS NOT NULL AND NEW.attempt_id IS NULL)
    OR (OLD.ticket_id IS NOT NULL AND NEW.ticket_id IS NULL)
    OR (OLD.recording_id IS NOT NULL AND NEW.recording_id IS NULL)
    OR (OLD.participant_id IS NOT NULL AND NEW.participant_id IS NULL) THEN
  IF (NEW.attempt_id IS DISTINCT FROM OLD.attempt_id AND NEW.attempt_id IS NOT NULL)
     OR (NEW.ticket_id IS DISTINCT FROM OLD.ticket_id AND NEW.ticket_id IS NOT NULL)
     OR (NEW.recording_id IS DISTINCT FROM OLD.recording_id AND NEW.recording_id IS NOT NULL)
     OR (NEW.participant_id IS DISTINCT FROM OLD.participant_id AND NEW.participant_id IS NOT NULL)
     OR NEW.id IS DISTINCT FROM OLD.id
     OR NEW.user_id IS DISTINCT FROM OLD.user_id
     OR NEW.participant_code IS DISTINCT FROM OLD.participant_code
     OR NEW.evaluation_session_id IS DISTINCT FROM OLD.evaluation_session_id
     OR NEW.channel IS DISTINCT FROM OLD.channel
     OR NEW.source_mode IS DISTINCT FROM OLD.source_mode
     OR NEW.transcript IS DISTINCT FROM OLD.transcript
     OR NEW.raw_classifier_json IS DISTINCT FROM OLD.raw_classifier_json
     OR NEW.validated_payload_json IS DISTINCT FROM OLD.validated_payload_json
     OR NEW.initial_request_kind IS DISTINCT FROM OLD.initial_request_kind
     OR NEW.initial_impact IS DISTINCT FROM OLD.initial_impact
     OR NEW.initial_urgency IS DISTINCT FROM OLD.initial_urgency
     OR NEW.initial_category IS DISTINCT FROM OLD.initial_category
     OR NEW.initial_reason IS DISTINCT FROM OLD.initial_reason
     OR NEW.initial_priority IS DISTINCT FROM OLD.initial_priority
     OR NEW.classification_status IS DISTINCT FROM OLD.classification_status
     OR NEW.priority_source IS DISTINCT FROM OLD.priority_source
     OR NEW.is_provisional IS DISTINCT FROM OLD.is_provisional
     OR NEW.has_mixed_requests IS DISTINCT FROM OLD.has_mixed_requests
     OR NEW.in_scope IS DISTINCT FROM OLD.in_scope
     OR NEW.scope_reason IS DISTINCT FROM OLD.scope_reason
     OR NEW.classifier_model IS DISTINCT FROM OLD.classifier_model
     OR NEW.classifier_config_json IS DISTINCT FROM OLD.classifier_config_json
     OR NEW.prompt_version IS DISTINCT FROM OLD.prompt_version
     OR NEW.policy_version IS DISTINCT FROM OLD.policy_version
     OR NEW.software_version IS DISTINCT FROM OLD.software_version
     OR NEW.build_commit IS DISTINCT FROM OLD.build_commit
     OR NEW.commit_dirty IS DISTINCT FROM OLD.commit_dirty
     OR NEW.error_code IS DISTINCT FROM OLD.error_code
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
   RAISE EXCEPTION 'La evidencia inicial de clasificación es inmutable';
  END IF;
  RETURN NEW;
 END IF;
 RAISE EXCEPTION 'La evidencia inicial de clasificación es inmutable';
END $$;

DROP TRIGGER IF EXISTS classification_snapshots_immutable_guard ON classification_snapshots;
CREATE TRIGGER classification_snapshots_immutable_guard
 BEFORE UPDATE ON classification_snapshots
 FOR EACH ROW EXECUTE FUNCTION enforce_classification_snapshot_immutability();

CREATE TABLE IF NOT EXISTS ticket_classification_changes (
 id CHAR(36) PRIMARY KEY,
 ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
 snapshot_id CHAR(36) REFERENCES classification_snapshots(id) ON DELETE SET NULL,
 changed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 participant_id CHAR(36) REFERENCES research_participants(id) ON DELETE SET NULL,
 participant_code VARCHAR(30),
 evaluation_session_id VARCHAR(64),
 previous_request_kind VARCHAR(20) NOT NULL,
 new_request_kind VARCHAR(20) NOT NULL,
 previous_priority VARCHAR(20) NOT NULL,
 new_priority VARCHAR(20) NOT NULL,
 change_reason TEXT NOT NULL,
 was_provisional BOOLEAN,
 policy_version VARCHAR(40) NOT NULL,
 software_version VARCHAR(30) NOT NULL,
 build_commit VARCHAR(64),
 commit_dirty BOOLEAN,
 changed_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_classification_changes_ticket ON ticket_classification_changes(ticket_id, changed_at);

CREATE OR REPLACE FUNCTION enforce_classification_change_immutability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (OLD.snapshot_id IS NOT NULL AND NEW.snapshot_id IS NULL)
    OR (OLD.changed_by IS NOT NULL AND NEW.changed_by IS NULL)
    OR (OLD.participant_id IS NOT NULL AND NEW.participant_id IS NULL) THEN
  IF (NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id AND NEW.snapshot_id IS NOT NULL)
     OR (NEW.changed_by IS DISTINCT FROM OLD.changed_by AND NEW.changed_by IS NOT NULL)
     OR (NEW.participant_id IS DISTINCT FROM OLD.participant_id AND NEW.participant_id IS NOT NULL)
     OR NEW.id IS DISTINCT FROM OLD.id
     OR NEW.ticket_id IS DISTINCT FROM OLD.ticket_id
     OR NEW.participant_code IS DISTINCT FROM OLD.participant_code
     OR NEW.evaluation_session_id IS DISTINCT FROM OLD.evaluation_session_id
     OR NEW.previous_request_kind IS DISTINCT FROM OLD.previous_request_kind
     OR NEW.new_request_kind IS DISTINCT FROM OLD.new_request_kind
     OR NEW.previous_priority IS DISTINCT FROM OLD.previous_priority
     OR NEW.new_priority IS DISTINCT FROM OLD.new_priority
     OR NEW.change_reason IS DISTINCT FROM OLD.change_reason
     OR NEW.was_provisional IS DISTINCT FROM OLD.was_provisional
     OR NEW.policy_version IS DISTINCT FROM OLD.policy_version
     OR NEW.software_version IS DISTINCT FROM OLD.software_version
     OR NEW.build_commit IS DISTINCT FROM OLD.build_commit
     OR NEW.commit_dirty IS DISTINCT FROM OLD.commit_dirty
     OR NEW.changed_at IS DISTINCT FROM OLD.changed_at THEN
   RAISE EXCEPTION 'El historial de cambios de clasificación es de solo anexo';
  END IF;
  RETURN NEW;
 END IF;
 RAISE EXCEPTION 'El historial de cambios de clasificación es de solo anexo';
END $$;

DROP TRIGGER IF EXISTS ticket_classification_changes_immutable_guard ON ticket_classification_changes;
CREATE TRIGGER ticket_classification_changes_immutable_guard
 BEFORE UPDATE ON ticket_classification_changes
 FOR EACH ROW EXECUTE FUNCTION enforce_classification_change_immutability();

ALTER TABLE classification_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_classification_changes ENABLE ROW LEVEL SECURITY;
