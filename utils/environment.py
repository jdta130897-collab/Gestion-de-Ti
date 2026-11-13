"""Las credenciales de producción proceden exclusivamente del entorno del servidor."""
import os
from dotenv import load_dotenv


def is_production_environment():
    return bool(os.getenv('VERCEL')) or os.getenv('APP_ENV', '').lower() == 'production'


def load_local_environment():
    if not is_production_environment():
        load_dotenv()
