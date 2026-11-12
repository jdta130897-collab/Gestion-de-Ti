import random
import string
import re
import os
from datetime import datetime, timedelta


def generate_random_string(length=10):
    """Genera una cadena aleatoria de caracteres."""
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(length)
    )


def generate_password_reset_token():
    """Genera un token para restablecer contraseña."""
    return "".join(random.choice(string.digits) for _ in range(6))


def format_date(date, format_str="%d/%m/%Y"):
    """Formatea una fecha en un formato específico."""
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return date

    if date:
        return date.strftime(format_str)
    return ""


def format_datetime(dt, format_str="%d/%m/%Y %H:%M"):
    """Formatea una fecha y hora en un formato específico."""
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return dt

    if dt:
        return dt.strftime(format_str)
    return ""


def translate_asset_type(asset_type):
    """Traduce el tipo de activo a español."""
    translations = {
        "hardware": "Equipo físico",
        "software": "Programa informático",
        "network": "Red",
        "peripheral": "Periférico",
        "other": "Otro",
    }
    return translations.get(asset_type, asset_type)


def translate_asset_status(asset_status):
    """Traduce el estado del activo a español."""
    translations = {
        "active": "Activo",
        "maintenance": "Mantenimiento",
        "retired": "Retirado",
        "storage": "Almacenado",
    }
    return translations.get(asset_status, asset_status)


def translate_ticket_status(ticket_status):
    """Traduce el estado del ticket a español."""
    translations = {
        "open": "Abierto",
        "in_progress": "En progreso",
        "resolved": "Resuelto",
        "closed": "Cerrado",
    }
    return translations.get(ticket_status, ticket_status)


def translate_ticket_priority(ticket_priority):
    """Traduce la prioridad del ticket a español."""
    translations = {
        "low": "Baja",
        "medium": "Media",
        "high": "Alta",
        "critical": "Crítica",
    }
    return translations.get(ticket_priority, ticket_priority)


def get_asset_badge_color(asset_status):
    """Devuelve el color de la insignia para un estado de activo."""
    colors = {
        "active": "success",
        "maintenance": "warning",
        "retired": "danger",
        "storage": "secondary",
    }
    return colors.get(asset_status, "primary")


def time_since(dt):
    """Calcula el tiempo transcurrido desde una fecha."""
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "hace menos de un minuto"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"hace {minutes} {'minuto' if minutes == 1 else 'minutos'}"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"hace {hours} {'hora' if hours == 1 else 'horas'}"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"hace {days} {'día' if days == 1 else 'días'}"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"hace {weeks} {'semana' if weeks == 1 else 'semanas'}"
    else:
        return format_date(dt, "%Y-%m-%d")


def sanitize_string(s):
    """Sanitiza una cadena para evitar inyecciones."""
    if not s:
        return ""
    # Eliminar caracteres especiales
    return re.sub(r'[<>"\'&;]', "", s)


def truncate_string(s, max_length=100, suffix="..."):
    """Trunca una cadena si excede la longitud máxima."""
    if not s:
        return ""
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def calculate_metrics_stats(metrics):
    """Calcula estadísticas de métricas (mínimo, máximo, promedio)."""
    if not metrics:
        return {"min": 0, "max": 0, "avg": 0, "count": 0}

    values = [m["metric_value"] for m in metrics]

    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "count": len(values),
    }


def get_date_range(range_type):
    """Obtiene rango de fechas según tipo (día, semana, mes, año)."""
    now = datetime.now()

    if range_type == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif range_type == "week":
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif range_type == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif range_type == "year":
        start_date = now.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end_date = now
    else:  # Si no se especifica, devolver últimas 24 horas
        start_date = now - timedelta(hours=24)
        end_date = now

    return start_date, end_date


def translate_user_role(role):
    from utils.permissions import ROLE_LABELS
    return ROLE_LABELS.get(role, role)


def translate_metric_name(name):
    return {
        "cpu_usage": "Uso del procesador", "cpu": "Procesador",
        "memory_usage": "Uso de memoria", "memory": "Memoria",
        "disk_usage": "Uso del disco", "disk": "Disco",
        "temperature": "Temperatura", "cpu_temperature": "Temperatura del procesador",
        "network_usage": "Uso de la red", "uptime": "Tiempo de actividad",
    }.get(name, name)
