"""Trazabilidad inmutable de clasificación inicial y cambios humanos posteriores."""
import json
import uuid
from config.database import Database
from utils.release import POLICY_VERSION, PROMPT_VERSION, get_evaluation_session_id, get_release_metadata
from utils.timezone import utc_now as _utc_naive


class ClassificationTraceService:
    @staticmethod
    def _json_dumps(value):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @classmethod
    def save_snapshot(cls, data, tx=None):
        release = get_release_metadata()
        snapshot_id = str(uuid.uuid4())
        now = _utc_naive()
        sql = '''INSERT INTO classification_snapshots (
            id, attempt_id, ticket_id, recording_id, user_id, participant_id, participant_code,
            evaluation_session_id, channel, source_mode, transcript, raw_classifier_json,
            validated_payload_json, initial_request_kind, initial_impact, initial_urgency,
            initial_category, initial_reason, initial_priority, classification_status,
            priority_source, is_provisional, has_mixed_requests, in_scope, scope_reason,
            classifier_model, classifier_config_json, prompt_version, policy_version,
            software_version, build_commit, commit_dirty, error_code, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
        params = (
            snapshot_id,
            data.get('attempt_id'),
            data.get('ticket_id'),
            data.get('recording_id'),
            data.get('user_id'),
            data.get('participant_id'),
            data.get('participant_code'),
            data.get('evaluation_session_id') if 'evaluation_session_id' in data else get_evaluation_session_id(),
            data['channel'],
            data['source_mode'],
            data.get('transcript'),
            cls._json_dumps(data.get('raw_classifier_json')),
            cls._json_dumps(data.get('validated_payload_json')),
            data.get('initial_request_kind'),
            data.get('initial_impact'),
            data.get('initial_urgency'),
            data.get('initial_category'),
            data.get('initial_reason'),
            data.get('initial_priority'),
            data.get('classification_status'),
            data.get('priority_source'),
            bool(data.get('is_provisional', False)),
            data.get('has_mixed_requests'),
            data.get('in_scope'),
            data.get('scope_reason'),
            data.get('classifier_model'),
            cls._json_dumps(data.get('classifier_config_json')),
            data.get('prompt_version') if 'prompt_version' in data else (PROMPT_VERSION if data['channel'] == 'voice' else None),
            data.get('policy_version') or POLICY_VERSION,
            data.get('software_version') or release['version'],
            data.get('build_commit') if 'build_commit' in data else (release['commit'] or None),
            data.get('commit_dirty') if 'commit_dirty' in data else release['dirty'],
            data.get('error_code'),
            now,
        )
        if tx is not None:
            tx.execute(sql, params)
        else:
            Database().execute_update(sql, params)
        return snapshot_id

    @classmethod
    def record_human_change(cls, data, tx=None):
        release = get_release_metadata()
        change_id = str(uuid.uuid4())
        now = _utc_naive()
        sql = '''INSERT INTO ticket_classification_changes (
            id, ticket_id, snapshot_id, changed_by, participant_id, participant_code,
            evaluation_session_id, previous_request_kind, new_request_kind,
            previous_priority, new_priority, change_reason, was_provisional,
            policy_version, software_version, build_commit, commit_dirty, changed_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
        params = (
            change_id,
            data['ticket_id'],
            data.get('snapshot_id'),
            data.get('changed_by'),
            data.get('participant_id'),
            data.get('participant_code'),
            data.get('evaluation_session_id') if 'evaluation_session_id' in data else get_evaluation_session_id(),
            data['previous_request_kind'],
            data['new_request_kind'],
            data['previous_priority'],
            data['new_priority'],
            data['change_reason'],
            data.get('was_provisional'),
            data.get('policy_version') or POLICY_VERSION,
            data.get('software_version') or release['version'],
            data.get('build_commit') if 'build_commit' in data else (release['commit'] or None),
            data.get('commit_dirty') if 'commit_dirty' in data else release['dirty'],
            now,
        )
        if tx is not None:
            tx.execute(sql, params)
        else:
            Database().execute_update(sql, params)
        return change_id

    @staticmethod
    def get_ticket_trace(ticket_id):
        db = Database()
        snapshots = db.execute_query(
            'SELECT * FROM classification_snapshots WHERE ticket_id=%s ORDER BY created_at ASC LIMIT 1',
            (ticket_id,),
        )
        changes = db.execute_query(
            '''SELECT c.*, u.name AS changed_by_name
               FROM ticket_classification_changes c
               LEFT JOIN users u ON u.id = c.changed_by
               WHERE c.ticket_id=%s
               ORDER BY c.changed_at ASC, c.id ASC''',
            (ticket_id,),
        )
        return (snapshots[0] if snapshots else None), changes
