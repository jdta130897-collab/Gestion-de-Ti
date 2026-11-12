-- Los audios se guardan en PostgreSQL, nunca en archivos estáticos o buckets públicos.
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS software_version VARCHAR(30);
ALTER TABLE creation_attempts ADD COLUMN IF NOT EXISTS build_commit VARCHAR(64);
CREATE TABLE IF NOT EXISTS research_participants (
 id CHAR(36) PRIMARY KEY,
 user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
 code VARCHAR(30) NOT NULL UNIQUE,
 created_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_recordings (
 id CHAR(36) PRIMARY KEY,
 attempt_id CHAR(36) NOT NULL UNIQUE REFERENCES creation_attempts(id) ON DELETE CASCADE,
 participant_id CHAR(36) NOT NULL REFERENCES research_participants(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 ticket_id INTEGER REFERENCES tickets(id) ON DELETE SET NULL,
 software_version VARCHAR(30) NOT NULL, build_commit VARCHAR(64),
 mime_type VARCHAR(50) NOT NULL, byte_size INTEGER NOT NULL CHECK (byte_size>0 AND byte_size<=3900000),
 sha256 CHAR(64) NOT NULL, audio_data BYTEA NOT NULL,
 transcript TEXT, outcome VARCHAR(20) NOT NULL DEFAULT 'processing'
 CHECK (outcome IN ('processing','success','failed')),
 error_code VARCHAR(100), consent_at TIMESTAMP NOT NULL,
 created_at TIMESTAMP NOT NULL, completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_recordings_owner ON voice_recordings(user_id,created_at);
CREATE INDEX IF NOT EXISTS ix_recordings_ticket ON voice_recordings(ticket_id);
ALTER TABLE research_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_recordings ENABLE ROW LEVEL SECURITY;
