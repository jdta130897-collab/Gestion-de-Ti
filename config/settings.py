import os
from utils.environment import load_local_environment

load_local_environment()

# Configuración de la aplicación
APP_NAME = "Sistema de Gestión TI"
from utils.release import SOFTWARE_VERSION
APP_VERSION = SOFTWARE_VERSION
DEBUG = os.getenv("DEBUG", "False") == "True"

# Configuración de la base de datos
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "ti_management")

# Configuración del servidor
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 5000))

# Configuración de email
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "")

# Configuración de seguridad
SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta_predeterminada")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False") == "True"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
API_KEY_EXPIRY_DAYS = int(os.getenv("API_KEY_EXPIRY_DAYS", 30))

# Configuración de monitoreo
MONITORING_INTERVAL = int(os.getenv("MONITORING_INTERVAL", 300))  # en segundos
