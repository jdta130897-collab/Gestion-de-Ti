"""Protección contra ejecución accidental de pruebas o semillas sobre producción."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
BLOCKED_HOST_MARKERS = (
    "supabase.co",
    "supabase.com",
    "pooler.supabase",
    "neon.tech",
    "rds.amazonaws.com",
    "azure.com",
    "render.com",
    "railway.app",
    "vercel",
)


def load_test_env():
    """Carga variables de prueba de forma explícita y sin leer archivos de producción."""
    env_test = ROOT_DIR / ".env.test"
    env_default = ROOT_DIR / ".env"
    app_env = (os.getenv("APP_ENV") or "").strip().lower()

    if app_env == "test" and env_test.exists():
        # No sobrescribe variables explícitas del proceso (permite probar/bloquear URLs inyectadas).
        load_dotenv(env_test, override=False)
    elif env_test.exists() and not os.getenv("DATABASE_URL") and not os.getenv("DB_NAME") and not env_default.exists():
        load_dotenv(env_test, override=False)
    elif env_default.exists():
        load_dotenv(env_default, override=False)


def _validate_db_name(db_name, engine):
    normalized = (db_name or "").strip().lower()
    if not normalized:
        raise RuntimeError(f"Bloqueado ({engine}): no se especificó nombre de base de datos de pruebas.")
    if "test" not in normalized and "prueba" not in normalized:
        raise RuntimeError(
            f"Bloqueado ({engine}): la base '{db_name}' no está identificada como base de pruebas "
            "(el nombre debe incluir 'test' o 'prueba', p. ej. 'ti_management_test')."
        )


def assert_test_database():
    """Impide ejecutar pruebas o sembrado de datos contra una base de producción o remota."""
    load_test_env()

    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
        raise RuntimeError("Bloqueado: no se permite ejecutar pruebas en entorno Vercel/producción.")

    app_env = (os.getenv("APP_ENV") or "").strip().lower()
    if app_env in ("prod", "production"):
        raise RuntimeError("Bloqueado: APP_ENV indica producción.")

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if database_url:
        parsed = urlsplit(database_url)
        host = (parsed.hostname or "").strip().lower()
        lowered_url = database_url.lower()
        if any(marker in lowered_url for marker in BLOCKED_HOST_MARKERS):
            raise RuntimeError(
                "Bloqueado: DATABASE_URL apunta a un proveedor externo o de producción. "
                "Usa una base PostgreSQL local exclusiva de pruebas."
            )
        if host not in LOCAL_HOSTS:
            raise RuntimeError(
                f"Bloqueado: el host PostgreSQL '{host or 'desconocido'}' no es local "
                f"(permitidos: {', '.join(sorted(LOCAL_HOSTS))})."
            )
        db_name = parsed.path.lstrip("/")
        _validate_db_name(db_name, "PostgreSQL")
        return {
            "engine": "postgresql",
            "host": host,
            "port": parsed.port or 5432,
            "database": db_name,
        }

    db_host = (os.getenv("DB_HOST") or "localhost").strip().lower()
    db_name = (os.getenv("DB_NAME") or "ti_management").strip()
    if any(marker in db_host for marker in BLOCKED_HOST_MARKERS) or db_host not in LOCAL_HOSTS:
        raise RuntimeError(
            f"Bloqueado: el host MySQL '{db_host}' no es local."
        )
    _validate_db_name(db_name, "MySQL")
    return {
        "engine": "mysql",
        "host": db_host,
        "port": int(os.getenv("DB_PORT", "3306")),
        "database": db_name,
    }
