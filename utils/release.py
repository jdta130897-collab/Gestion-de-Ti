"""Versión del software identificable sin depender de la base de datos."""
import os
from pathlib import Path

SOFTWARE_VERSION = (Path(__file__).resolve().parents[1] / 'VERSION').read_text(encoding='utf-8').strip()
BUILD_COMMIT = os.getenv('VERCEL_GIT_COMMIT_SHA', '')
