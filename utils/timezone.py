"""Utilidades compartidas de fecha y hora: almacenamiento UTC y visualización Lima (UTC-5)."""
from datetime import datetime, timedelta, timezone

LIMA_OFFSET = timedelta(hours=-5)
LIMA_TZ = timezone(LIMA_OFFSET)
TIMEZONE_NAME = "America/Lima"
UTC_OFFSET_LABEL = "UTC-5"


def utc_now():
    """Devuelve la fecha/hora actual en UTC sin tzinfo (compatible con PostgreSQL TIMESTAMP y MySQL DATETIME)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def lima_now():
    """Devuelve la fecha/hora actual en horario de Lima (UTC-5) sin tzinfo para etiquetas visuales."""
    return datetime.now(LIMA_TZ).replace(tzinfo=None)


def to_lima(dt):
    """Convierte un datetime UTC naive a hora local de Lima (UTC-5)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(LIMA_TZ).replace(tzinfo=None)
    return dt + LIMA_OFFSET


def utc_iso(dt):
    """Serializa un datetime UTC naive en formato ISO-8601 con sufijo Z."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


def lima_day_bounds_to_utc(date_from=None, date_to=None):
    """Convierte límites de fecha calendario en Lima (00:00..23:59:59) a rango [inicio, fin_exclusivo) en UTC."""
    utc_start = (date_from - LIMA_OFFSET) if date_from is not None else None
    utc_end_exclusive = (date_to + timedelta(days=1) - LIMA_OFFSET) if date_to is not None else None
    return utc_start, utc_end_exclusive
