"""Copia transaccional: MySQL local -> PostgreSQL vacío; conserva IDs y hashes.

No produce dumps ni publica credenciales. Se niega a sobrescribir datos de destino.
DATABASE_URL selecciona el destino y DB_* selecciona el origen local.
"""
import os
import sys
from pathlib import Path
import mysql.connector
import psycopg
from psycopg import sql
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
load_dotenv(root / '.env')
from scripts.migrate_postgres import migrate

TABLES = ('areas','users','assets','tickets','ticket_comments','monitoring_data','api_keys','creation_attempts','notifications')


def transfer():
    migrate()
    source = mysql.connector.connect(host=os.getenv('DB_HOST','127.0.0.1'), port=int(os.getenv('DB_PORT','3306')),
        user=os.getenv('DB_USER','root'), password=os.getenv('DB_PASSWORD',''), database=os.getenv('DB_NAME','ti_management'))
    counts = {}
    try:
        source.start_transaction(consistent_snapshot=True, readonly=True)
        cursor = source.cursor(dictionary=True)
        with psycopg.connect(os.environ['DATABASE_URL'], prepare_threshold=None) as target:
            for table in TABLES:
                count = target.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                if count:
                    raise RuntimeError('Destino con datos: se cancela la copia sin sobrescribir registros.')
            for table in TABLES:
                cursor.execute('SELECT * FROM ' + table)
                rows = cursor.fetchall()
                for row in rows:
                    if 'is_active' in row:
                        row['is_active'] = bool(row['is_active'])
                    statement = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),
                        sql.SQL(',').join(map(sql.Identifier, row)), sql.SQL(',').join(sql.Placeholder() for _ in row))
                    target.execute(statement, list(row.values()))
                if table != 'creation_attempts':
                    target.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s,'id'), COALESCE(MAX(id),1), COUNT(*)>0) FROM {}").format(sql.Identifier(table)), (table,))
                counts[table] = target.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                if counts[table] != len(rows):
                    raise RuntimeError('La verificación de filas no coincide. Transacción cancelada.')
        cursor.close()
    finally:
        source.rollback()
        source.close()
    print('Copia verificada (usuarios y contraseñas conservados):', counts)


if __name__ == '__main__':
    transfer()
