"""Versión del software, commit real y bandera de cambios locales sin depender de la base de datos."""
import os
import subprocess
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_VERSION = (_REPO_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
POLICY_VERSION = '1.1.0-etapa5'
PROMPT_VERSION = 'voice-prompt-v2-etapa2'
PROTOCOL_VERSION = '1.0.0-etapa6'
CAMPAIGN_ID_DEFAULT = 'CAMP-INGENIARE-FINAL-2026'


def _run_git(*args):
    try:
        proc = subprocess.run(
            ['git', *args],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ''


def get_release_metadata():
    """Devuelve versión, commit real (entorno o git local) y si hay cambios locales sin confirmar."""
    env_commit = (
        os.getenv('VERCEL_GIT_COMMIT_SHA', '').strip()
        or os.getenv('BUILD_COMMIT', '').strip()
        or os.getenv('GIT_COMMIT', '').strip()
    )
    local_commit = ''
    dirty = False
    if (_REPO_ROOT / '.git').exists():
        local_commit = _run_git('rev-parse', 'HEAD')
        # git status --porcelain ignora automáticamente .env, .env.test, .runtime y .venv (.gitignore)
        dirty = bool(_run_git('status', '--porcelain'))

    packaged = {}
    if (_REPO_ROOT / 'release.json').is_file():
        packaged = json.loads((_REPO_ROOT / 'release.json').read_text(encoding='utf-8'))
    commit = env_commit or local_commit or packaged.get('source_commit', '')
    if not env_commit and not local_commit and packaged.get('source_dirty'):
        dirty = True
    if os.getenv('BUILD_COMMIT_DIRTY', '').lower() in ('1', 'true', 'yes'):
        dirty = True

    return {
        'version': SOFTWARE_VERSION,
        'commit': commit,
        'dirty': dirty,
        'commit_display': f'{commit}+dirty' if (commit and dirty) else commit,
        'policy_version': POLICY_VERSION,
        'prompt_version': PROMPT_VERSION,
        'protocol_version': PROTOCOL_VERSION,
        'source_sha256': packaged.get('source_sha256'),
    }


def get_evaluation_session_id():
    """Obtiene el identificador explícito de sesión de evaluación si existe en entorno o sesión HTTP."""
    env_session = os.getenv('EVALUATION_SESSION_ID', '').strip()
    if env_session:
        return env_session[:64]
    try:
        from flask import has_request_context, session, request
        if has_request_context():
            val = (
                session.get('evaluation_session_id')
                or request.headers.get('X-Evaluation-Session')
                or ''
            )
            val = str(val).strip()
            if val:
                return val[:64]
    except Exception:
        pass
    return None


_INITIAL = get_release_metadata()
BUILD_COMMIT = _INITIAL['commit']
COMMIT_DIRTY = _INITIAL['dirty']
