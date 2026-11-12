"""Aplica el esquema aditivo de PostgreSQL. No crea usuarios ni datos ficticios."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
load_dotenv(root / '.env')


def migrate():
    import psycopg
    if not os.getenv('DATABASE_URL'):
        raise SystemExit('Falta DATABASE_URL de PostgreSQL/Supabase.')
    with psycopg.connect(os.environ['DATABASE_URL'], prepare_threshold=None) as conn:
        for path in sorted((root / 'supabase/migrations').glob('*.sql')):
            conn.execute(path.read_text(encoding='utf-8'), prepare=False)
    print('Esquema PostgreSQL actualizado sin borrar registros.')


if __name__ == '__main__':
    migrate()
