-- Migración aditiva (Etapa 4): separación de tiempos de navegador vs servidor,
-- registro de pausas durante preparación y motivo explícito de resultados/bordes.
-- Conserva íntegramente registros previos sin completar retrospectivamente valores desconocidos.

ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS outcome_reason VARCHAR(60);
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS pause_count INTEGER;
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS paused_ms DOUBLE PRECISION;
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS client_prep_ms DOUBLE PRECISION;
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS client_confirmed_at TIMESTAMP;
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS browser_roundtrip_ms DOUBLE PRECISION;
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS browser_total_ms DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS ix_attempt_outcome_started ON creation_attempts(outcome, started_at);
