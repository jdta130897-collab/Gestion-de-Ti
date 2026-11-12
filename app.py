import os
import sys
from gtts import gTTS
from datetime import datetime, date
from dotenv import load_dotenv
load_dotenv()
if os.getenv('VERCEL') and (not os.getenv('DATABASE_URL') or not os.getenv('SECRET_KEY') or os.getenv('SECRET_KEY') == 'clave_secreta_predeterminada'):
    raise RuntimeError('Configura DATABASE_URL y una SECRET_KEY privada antes del despliegue.')
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, jsonify
from controllers.ticket_controller import TicketController
from services.voice_service import VoiceService

voice_service = VoiceService()

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'webm'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Cargar variables de entorno
load_dotenv()

# Agregar ruta base al path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Cargar utilidades
from utils.permissions import (
    as_template_context,
    can_assign_tickets,
    can_delete_tickets,
    can_manage_assets,
    can_manage_users,
    can_monitor,
    can_see_ticket,
    can_view_assets,
    can_work_tickets,
)
from utils.helpers import (
    format_date,
    format_datetime,
    translate_asset_type,
    translate_user_role,
    translate_metric_name,
    translate_asset_status,
    translate_ticket_status,
    translate_ticket_priority,
    get_asset_badge_color,
)

# Importar controladores (con manejo de errores)
AssetController = None
UserController = None
TicketController = None
MonitoringController = None
Database = None
AuthService = None

try:
    from controllers.asset_controller import AssetController
    from controllers.user_controller import UserController
    from controllers.ticket_controller import TicketController
    from controllers.monitoring_controller import MonitoringController
    from config.database import Database
    from services.auth_service import AuthService
except ImportError as e:
    print(f"Error al importar módulos: {e}")


"""
Aplicación principal del Sistema de Gestión TI.
Este archivo contiene la configuración y rutas de la aplicación Flask.
"""

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    session,
    redirect,
    url_for,
    flash,
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Asegurar que los módulos del proyecto estén en el path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Importar controladores
try:
    from controllers.asset_controller import AssetController
    from controllers.ticket_controller import TicketController
    from controllers.monitoring_controller import MonitoringController
    from controllers.user_controller import UserController
    from services.auth_service import AuthService
    from config.database import Database
except ImportError as e:
    print(f"Error al importar módulos: {e}")
    # Importaciones mínimas para funcionamiento básico
    Database = None
    AssetController = None
    TicketController = None
    MonitoringController = None
    UserController = None
    AuthService = None

# Cargar variables de entorno
load_dotenv()


# Funciones de utilidad para plantillas
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
        return dt.strftime("%Y-%m-%d")


def format_date(date_obj, format_str="%Y-%m-%d"):
    """Formatea un objeto date o datetime."""
    if isinstance(date_obj, (datetime, date)):
        return date_obj.strftime(format_str)
    return str(date_obj) if date_obj else ""


def format_datetime(datetime_obj, format_str="%Y-%m-%d %H:%M:%S"):
    """Formatea un objeto datetime."""
    if isinstance(datetime_obj, datetime):
        return datetime_obj.strftime(format_str)
    return str(datetime_obj) if datetime_obj else ""


def truncate_string(s, max_length=100, suffix="..."):
    """Trunca una cadena si excede la longitud máxima."""
    if not s:
        return ""
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


# Crear aplicación Flask
app = Flask(__name__, template_folder="views/templates", static_folder="views/static")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
app.secret_key = os.getenv("SECRET_KEY", "clave_secreta_predeterminada")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
app.config.update(SESSION_COOKIE_SECURE=bool(os.getenv('VERCEL')) or os.getenv('SESSION_COOKIE_SECURE','False') == 'True', SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
from controllers.area_routes import areas_bp
from services.area_service import AreaService
from utils.permissions import is_super_admin
app.register_blueprint(areas_bp)
from controllers.insight_routes import insights_bp
from services.measurement_service import measure_submission
app.register_blueprint(insights_bp)


# Variables globales para templates
@app.context_processor
def utility_processor():
    return {
        "time_since": time_since,
        "format_date": format_date,
        "format_datetime": format_datetime,
        "translate_asset_type": translate_asset_type,
        "translate_user_role": translate_user_role,
        "translate_metric_name": translate_metric_name,
        "translate_asset_status": translate_asset_status,
        "translate_ticket_status": translate_ticket_status,
        "translate_ticket_priority": translate_ticket_priority,
        "get_asset_badge_color": get_asset_badge_color,
        "app_name": os.getenv("APP_NAME", "Sistema de Gestión TI"),
        "app_version": os.getenv("APP_VERSION", "1.0.0"),
        **as_template_context(),
        "available_areas": AreaService.all(active_only=True) if session.get('user_id') and is_super_admin() else [],
    }


def deny_access():
    flash("No tienes permiso para esta sección.", "error")
    return redirect(url_for("dashboard"))


# Middleware para verificar autenticación
@app.before_request
def check_auth():
    # Lista de rutas que no requieren autenticación
    public_routes = ["/login", "/register", "/static/", "/api/login", "/api/register", "/healthz"]

    # Verificar si la ruta actual es pública
    if any(request.path.startswith(route) for route in public_routes):
        return None

    # Verificar API key para rutas de API
    #if request.path.startswith("/api/"):
     #   api_key = request.headers.get("X-API-Key")
      #  if AuthService and not api_key:
       #     return jsonify({"status": "error", "message": "API key requerida"}), 401
        #if AuthService and not AuthService().validate_api_key(api_key):
         #   return jsonify({"status": "error", "message": "API key inválida"}), 401
       # return None

    # Verificar sesión para rutas web
    if "user_id" not in session:
        return redirect(url_for("login"))

    scope = AreaService.user_scope(session['user_id'])
    if not scope or not scope['is_active']:
        session.clear()
        return redirect(url_for('login'))
    session.update(user_role=scope['role'], area_id=scope['area_id'], area_code=scope['area_code'], area_name=scope['area_name'])
    if not scope['area_active'] and not is_super_admin():
        from flask import abort
        abort(403, description='Tu área está inactiva. Contacta al superadministrador.')

    # Comprobar tiempo de inactividad
    if "last_activity" in session:
        try:
            inactive_time = datetime.now() - datetime.fromisoformat(
                session["last_activity"]
            )
            if inactive_time > timedelta(hours=12):
                session.clear()
                flash("Tu sesión ha expirado por inactividad.")
                return redirect(url_for("login"))
        except:
            # Si hay error al parsear la fecha, simplemente actualizar
            pass

    # Actualizar tiempo de última actividad
    session["last_activity"] = datetime.now().isoformat()

    return None


#######################
# RUTAS WEB
#######################


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        result = UserController.login(request.form.get("email", ""), request.form.get("password", ""))
        if result.get("status") == "success":
            user = result["user"]
            session.clear()
            session.update(user_id=user["id"], user_name=user["name"], user_role=user["role"], last_activity=datetime.now().isoformat())
            return redirect(url_for("dashboard"))
        flash(result.get('message', 'Credenciales incorrectas'), "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Verificar si el registro está habilitado
    if os.getenv("ENABLE_REGISTRATION", "False") != "True":
        flash("El registro de nuevos usuarios está deshabilitado.")
        return redirect(url_for("login"))

    if request.method == "POST":
        # Obtener datos del formulario
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        # Validar datos
        if not name or not email or not password:
            flash("Todos los campos son obligatorios.")
            return render_template("register.html")

        if password != password_confirm:
            flash("Las contraseñas no coinciden.")
            return render_template("register.html")

        # Verificar si UserController está disponible
        if UserController is None:
            flash("El registro de usuarios no está disponible en este momento.")
            return redirect(url_for("login"))

        # Crear usuario (por defecto con rol "user")
        result = UserController.create_user(
            {"name": name, "email": email, "password": password, "role": "user"}
        )

        if result["status"] == "success":
            flash("Registro exitoso. Ahora puedes iniciar sesión.")
            return redirect(url_for("login"))
        else:
            flash(result["message"])

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    # Verificar si el usuario está autenticado
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Verificar si los controladores están disponibles
    # Si no hay conexión a la base de datos, usamos la versión simple
    if not all(
        [AssetController, TicketController, MonitoringController, UserController]
    ):
        return render_template("dashboard_simple.html")

    try:
        # Obtener estadísticas para el dashboard
        stats = {
            "assets": 0,
            "open_tickets": 0,
            "maintenance_assets": 0,
            "critical_tickets": 0,
        }

        # Intentar obtener activos
        if AssetController:
            assets_result = AssetController.get_all_assets()
            if assets_result["status"] == "success":
                assets = assets_result["data"]
                stats["assets"] = len(assets)
                stats["maintenance_assets"] = len(
                    [a for a in assets if a["status"] == "maintenance"]
                )

                # Ordenar por fecha de creación para obtener los más recientes
                recent_assets = sorted(
                    assets,
                    key=lambda x: (
                        x["created_at"]
                        if isinstance(x["created_at"], datetime)
                        else datetime.now()
                    ),
                    reverse=True,
                )[:5]
            else:
                recent_assets = []
        else:
            recent_assets = []

        # Intentar obtener tickets
        if TicketController:
            tickets_result = TicketController.get_all_tickets()
            if tickets_result["status"] == "success":
                tickets = tickets_result["data"]
                tickets = [t for t in tickets if can_see_ticket(t)]
                stats["open_tickets"] = len(
                    [t for t in tickets if t["status"] in ["open", "in_progress"]]
                )
                stats["critical_tickets"] = len(
                    [t for t in tickets if t["priority"] == "critical"]
                )

                # Ordenar por fecha de creación para obtener los más recientes
                recent_tickets = sorted(
                    tickets,
                    key=lambda x: (
                        x["created_at"]
                        if isinstance(x["created_at"], datetime)
                        else datetime.now()
                    ),
                    reverse=True,
                )[:5]
                stats["total_tickets"] = len(tickets)
                stats["in_progress"] = len([t for t in tickets if t["status"] == "in_progress"])
                stats["resolved"] = len([t for t in tickets if t["status"] in ("resolved", "closed")])
                stats["status_counts"] = {
                    "open": len([t for t in tickets if t["status"] == "open"]),
                    "in_progress": len([t for t in tickets if t["status"] == "in_progress"]),
                    "resolved": len([t for t in tickets if t["status"] == "resolved"]),
                    "closed": len([t for t in tickets if t["status"] == "closed"]),
                }
                stats["priority_counts"] = {
                    "low": len([t for t in tickets if t["priority"] == "low"]),
                    "medium": len([t for t in tickets if t["priority"] == "medium"]),
                    "high": len([t for t in tickets if t["priority"] == "high"]),
                    "critical": len([t for t in tickets if t["priority"] == "critical"]),
                }
            else:
                recent_tickets = []
        else:
            recent_tickets = []

        # Para simplificar, usemos funciones de utilidad adicionales
        def get_status_color(status):
            colors = {
                "open": "primary",
                "in_progress": "warning",
                "resolved": "success",
                "closed": "secondary",
            }
            return colors.get(status, "primary")

        def get_priority_color(priority):
            colors = {
                "low": "success",
                "medium": "warning",
                "high": "danger",
                "critical": "dark",
            }
            return colors.get(priority, "primary")

        # Verificar conexión a la base de datos
        db_connected = True
        hour = datetime.now().hour
        greeting = "Buenos días" if hour < 12 else "Buenas tardes" if hour < 19 else "Buenas noches"

        return render_template(
            "dashboard_simple.html",
            stats=stats,
            recent_assets=recent_assets,
            recent_tickets=recent_tickets,
            greeting=greeting,
            today_label=datetime.now().strftime("%d/%m/%Y"),
            get_status_color=get_status_color,
            get_priority_color=get_priority_color,
            db_connected=db_connected,
        )

    except Exception as e:
        print(f"Error en dashboard: {e}")
        # Si hay algún error, mostrar la versión simple
        return render_template("dashboard_simple.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente.")
    return redirect(url_for("login"))


# Rutas simplificadas para la versión básica
@app.route("/assets")
def assets_page():
    if not can_view_assets():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Verificar si el controlador está disponible
    if AssetController is None:
        return render_template("not_implemented.html", feature="Gestión de Activos")

    # Obtener parámetros de filtro
    filter_type = request.args.get("type", "")
    filter_status = request.args.get("status", "")
    filter_search = request.args.get("search", "")

    # Obtener activos
    result = AssetController.get_all_assets()
    assets = result["data"] if result["status"] == "success" else []

    # Aplicar filtros si están presentes
    if filter_type:
        assets = [a for a in assets if a["type"] == filter_type]
    if filter_status:
        assets = [a for a in assets if a["status"] == filter_status]
    if filter_search:
        assets = [a for a in assets if filter_search.lower() in a["name"].lower()]

    # Obtener tipos y estados para filtros
    asset_types = AssetController.get_asset_types()
    asset_statuses = AssetController.get_asset_statuses()

    return render_template(
        "assets/index.html",
        assets=assets,
        asset_types=asset_types,
        asset_statuses=asset_statuses,
    )


@app.route("/assets/create", methods=["GET", "POST"])
def create_asset():
    if not can_manage_assets():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Verificar si el controlador está disponible
    if AssetController is None:
        return render_template("not_implemented.html", feature="Gestión de Activos")

    if request.method == "POST":
        # Obtener datos del formulario
        asset_data = {
            "name": request.form.get("name"),
            "type": request.form.get("type"),
            "status": request.form.get("status"),
            "purchase_date": request.form.get("purchase_date"),
            "assigned_to": request.form.get("assigned_to") or None,
        }

        # Crear activo
        result = AssetController.create_asset(asset_data)

        if result["status"] == "success":
            flash("Activo creado correctamente.")
            return redirect(url_for("assets_page"))
        else:
            flash(result["message"])

    # Obtener datos para formulario
    asset_types = AssetController.get_asset_types()
    asset_statuses = AssetController.get_asset_statuses()
    users_result = AssetController.get_users_for_assignment()
    users = users_result["data"] if users_result["status"] == "success" else []

    return render_template(
        "assets/create.html",
        asset_types=asset_types,
        asset_statuses=asset_statuses,
        users=users,
    )


@app.route("/assets/<int:asset_id>")
def view_asset(asset_id):
    if not can_view_assets():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Verificar si el controlador está disponible
    if AssetController is None:
        return render_template("not_implemented.html", feature="Gestión de Activos")

    # Obtener detalles del activo
    result = AssetController.get_asset(asset_id)

    if result["status"] == "success":
        asset = result["data"]
        related_tickets = (
            []
        )  # En esta versión simple, no mostramos tickets relacionados

        return render_template(
            "assets/view.html", asset=asset, related_tickets=related_tickets
        )
    else:
        flash(result["message"])
        return redirect(url_for("assets_page"))


@app.route("/assets/<int:asset_id>/edit", methods=["GET", "POST"])
def edit_asset(asset_id):
    if not can_manage_assets():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Verificar si el controlador está disponible
    if AssetController is None:
        return render_template("not_implemented.html", feature="Gestión de Activos")

    # Obtener detalles del activo
    result = AssetController.get_asset(asset_id)

    if result["status"] != "success":
        flash(result["message"])
        return redirect(url_for("assets_page"))

    asset = result["data"]

    if request.method == "POST":
        # Obtener datos del formulario
        asset_data = {
            "name": request.form.get("name"),
            "type": request.form.get("type"),
            "status": request.form.get("status"),
            "purchase_date": request.form.get("purchase_date"),
            "assigned_to": request.form.get("assigned_to") or None,
        }

        # Actualizar activo
        update_result = AssetController.update_asset(asset_id, asset_data)

        if update_result["status"] == "success":
            flash("Activo actualizado correctamente.")
            return redirect(url_for("view_asset", asset_id=asset_id))
        else:
            flash(update_result["message"])

    # Obtener datos para formulario
    asset_types = AssetController.get_asset_types()
    asset_statuses = AssetController.get_asset_statuses()
    users_result = AssetController.get_users_for_assignment()
    users = users_result["data"] if users_result["status"] == "success" else []

    return render_template(
        "assets/edit.html",
        asset=asset,
        asset_types=asset_types,
        asset_statuses=asset_statuses,
        users=users,
    )


@app.route("/assets/<int:asset_id>/delete", methods=["POST"])
def delete_asset(asset_id):
    if not can_manage_assets():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Verificar si el controlador está disponible
    if AssetController is None:
        return render_template("not_implemented.html", feature="Gestión de Activos")

    # Eliminar activo
    result = AssetController.delete_asset(asset_id)

    if result["status"] == "success":
        flash("Activo eliminado correctamente.")
    else:
        flash(result["message"])

    return redirect(url_for("assets_page"))


@app.route("/tickets")
def tickets_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    # Obtener parámetros de filtrado desde la solicitud GET
    date_filter = request.args.get("date_filter")  # Formato: YYYY-MM-DD
    priority_filter = request.args.get("priority_filter")  # critical, high, medium, low

    result = TicketController.get_all_tickets(date_filter=date_filter, priority_filter=priority_filter)
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("dashboard"))

    tickets = result["data"]
    tickets = [item for item in tickets if can_see_ticket(item)]
    return render_template("tickets/index.html", tickets=tickets)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_all_tickets()
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("dashboard"))

    tickets = result["data"]
    return render_template("tickets/index.html", tickets=tickets)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_all_tickets()
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("dashboard"))

    tickets = result["data"]
    return render_template("tickets/index.html", tickets=tickets)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_all_tickets()
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("dashboard"))

    tickets = result["data"]
    return render_template("tickets/index.html", tickets=tickets)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_all_tickets()
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("dashboard"))

    tickets = result["data"]
    return render_template("tickets/index.html", tickets=tickets)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_all_tickets()
    tickets = result["data"] if result["status"] == "success" else []

    return render_template("tickets/index.html", tickets=tickets)

@app.route("/tickets/create", methods=["GET", "POST"])  # Cambiado de /tickets/new a /tickets/create
@measure_submission('manual')
def create_ticket():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    if request.method == "POST":
        ticket_data = {
            "title": request.form.get("subject"),
            "description": request.form.get("description"),
            "priority": request.form.get("priority"),
            "status": "open" if session.get("user_role") == "user" else request.form.get("status", "open"),
            "created_by": session.get("user_id"),
            "initial_comment": request.form.get("initial_comment", "Creado manualmente")
        }
        ticket_data['request_kind'] = request.form.get('request_kind', 'incident')
        ticket_data['origin_area_id'] = request.form.get('origin_area_id', type=int)
        result = TicketController.create_ticket(ticket_data)
        if result["status"] == "success":
            flash("Ticket creado correctamente", "success")
            return redirect(url_for("tickets_page"))
        else:
            flash(result["message"], "error")

    # Pasar prioridades y estados para los selectores
    priorities = ["low", "medium", "high", "critical"]
    statuses = ["open", "in_progress", "resolved", "closed"]
    return render_template("tickets/create.html", priorities=priorities, statuses=statuses)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    if request.method == "POST":
        ticket_data = {
            "title": request.form.get("subject"),
            "description": request.form.get("description"),
            "priority": request.form.get("priority"),
            "status": "open",
            "created_by": session.get("user_id"),
            "initial_comment": request.form.get("initial_comment", "Creado manualmente")
        }
        result = TicketController.create_ticket(ticket_data)
        if result["status"] == "success":
            flash("Ticket creado correctamente", "success")
            return redirect(url_for("tickets_page"))
        else:
            flash(result["message"], "error")

    # Pasar prioridades para el formulario
    priorities = ["low", "medium", "high", "critical"]
    return render_template("tickets/create.html", priorities=priorities)

@app.route("/tickets/<int:ticket_id>", methods=["GET", "POST"])
def view_ticket(ticket_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_ticket(ticket_id)
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("tickets_page"))

    # Extraer el ticket y los comentarios por separado
    ticket_data = result["data"]
    ticket = ticket_data["ticket"]  # Este es el diccionario del ticket real
    comments = ticket_data["comments"]
    if not can_see_ticket(ticket):
        return deny_access()

    if request.method == "POST":
        comment_text = request.form.get("comment")
        user_id = session.get("user_id")

        if comment_text and user_id:
            TicketController.add_comment(
                ticket_id, {"comment": comment_text, "user_id": user_id}
            )
            flash("Comentario agregado correctamente.", "success")
            return redirect(url_for("view_ticket", ticket_id=ticket_id))
        else:
            flash("Debe ingresar un comentario válido.", "error")
            return redirect(url_for("view_ticket", ticket_id=ticket_id))

    if request.args.get("preview") == "1":
        return render_template("tickets/preview.html", ticket=ticket, comments=comments, ticket_id=ticket_id)
    return render_template("tickets/view.html", ticket=ticket, comments=comments, ticket_id=ticket_id)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_ticket(ticket_id)
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("tickets_page"))

    ticket = result["data"]

    # Agregar comentario si POST
    if request.method == "POST":
        comment_text = request.form.get("comment")
        user_id = session.get("user_id")

        if comment_text and user_id:
            TicketController.add_comment(
                ticket_id, {"comment": comment_text, "user_id": user_id}
            )
            flash("Comentario agregado correctamente.", "success")
            return redirect(url_for("view_ticket", ticket_id=ticket_id))
        else:
            flash("Debe ingresar un comentario válido.", "error")
            return redirect(url_for("view_ticket", ticket_id=ticket_id))

    # Agregar return para GET request
    return render_template("tickets/view.html", ticket=ticket, ticket_id=ticket_id)


@app.route("/tickets/<int:ticket_id>/edit", methods=["GET", "POST"])
def edit_ticket(ticket_id):
    if not can_work_tickets():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_ticket(ticket_id)
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("tickets_page"))

    # Extraer el ticket y los comentarios por separado
    ticket_data = result["data"]
    ticket = ticket_data["ticket"]  # Este es el diccionario del ticket real
    comments = ticket_data["comments"]

    if request.method == "POST":
        ticket_data = {
            "title": request.form.get("subject"),  # Ajustado para coincidir con el formulario
            "description": request.form.get("description"),
            "priority": request.form.get("priority"),
            "status": request.form.get("status"),
            "update_comment": request.form.get("update_comment"),
            "updated_by": session.get("user_id")
        }
        if ticket_data['status'] in ('resolved', 'closed') and ticket['status'] != ticket_data['status'] and not (ticket_data.get('update_comment') or '').strip():
            flash('Registra una respuesta de TI antes de resolver o cerrar el reporte.', 'warning')
            return redirect(url_for('edit_ticket', ticket_id=ticket_id))
        if can_assign_tickets():
            ticket_data["assigned_to"] = request.form.get("assigned_to") or None
        result = TicketController.update_ticket(ticket_id, ticket_data)
        if result["status"] == "success":
            flash("Ticket actualizado correctamente", "success")
        else:
            flash(result["message"], "error")
        return redirect(url_for("view_ticket", ticket_id=ticket_id))

    # Pasar prioridades y estados para los selectores
    priorities = ["low", "medium", "high", "critical"]
    statuses = ["open", "in_progress", "resolved", "closed"]
    assignees = []
    if can_assign_tickets() and UserController:
        assignees = Database().execute_query("SELECT u.id,u.name,u.role FROM users u JOIN areas a ON a.id=u.area_id WHERE u.is_active=TRUE AND a.code='TI' AND u.role IN ('admin','manager','technician')")
    return render_template("tickets/edit.html", ticket=ticket, comments=comments, ticket_id=ticket_id, priorities=priorities, statuses=statuses, assignees=assignees)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_ticket(ticket_id)
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("tickets_page"))

    # Extraer el ticket y los comentarios por separado
    ticket_data = result["data"]
    ticket = ticket_data["ticket"]
    comments = ticket_data["comments"]

    if request.method == "POST":
        ticket_data = {
            "title": request.form.get("title"),
            "description": request.form.get("description"),
            "priority": request.form.get("priority"),
            "status": request.form.get("status"),
            "assigned_to": request.form.get("assigned_to") or None,
            "update_comment": request.form.get("update_comment"),
            "updated_by": session.get("user_id")
        }
        result = TicketController.update_ticket(ticket_id, ticket_data)
        if result["status"] == "success":
            flash("Ticket actualizado correctamente", "success")
        else:
            flash(result["message"], "error")
        return redirect(url_for("view_ticket", ticket_id=ticket_id))

    return render_template("tickets/edit.html", ticket=ticket, comments=comments, ticket_id=ticket_id)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_ticket(ticket_id)
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("tickets_page"))

    ticket = result["data"]

    if request.method == "POST":
        # Lógica para actualizar el ticket
        ticket_data = {
            "title": request.form.get("title"),
            "description": request.form.get("description"),
            "priority": request.form.get("priority"),
            "status": request.form.get("status"),
            "assigned_to": request.form.get("assigned_to") or None,
            "update_comment": request.form.get("update_comment"),
            "updated_by": session.get("user_id")
        }
        result = TicketController.update_ticket(ticket_id, ticket_data)
        if result["status"] == "success":
            flash("Ticket actualizado correctamente", "success")
        else:
            flash(result["message"], "error")
        return redirect(url_for("view_ticket", ticket_id=ticket_id))

    return render_template("tickets/edit.html", ticket=ticket, ticket_id=ticket_id)
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.get_ticket(ticket_id)
    if result["status"] != "success":
        flash(result["message"], "error")
        return redirect(url_for("tickets_page"))

    ticket = result["data"]

    if request.method == "POST":
        ticket_data = {
            "subject": request.form.get("subject"),
            "description": request.form.get("description"),
            "priority": request.form.get("priority"),
            "status": request.form.get("status"),
        }

        update_result = TicketController.update_ticket(ticket_id, ticket_data)

        if update_result["status"] == "success":
            flash("Ticket actualizado correctamente.", "success")
            return redirect(url_for("view_ticket", ticket_id=ticket_id))
        else:
            flash(update_result["message"], "error")

    priorities = ["low", "medium", "high", "critical"]
    statuses = ["open", "in_progress", "resolved", "closed"]

    return render_template(
        "tickets/edit.html", ticket=ticket, priorities=priorities, statuses=statuses
    )


@app.route("/tickets/<int:ticket_id>/delete", methods=["POST"])
def delete_ticket(ticket_id):
    if not can_delete_tickets():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.delete_ticket(ticket_id)
    if result["status"] == "success":
        flash("Ticket eliminado correctamente", "success")
    else:
        flash(result["message"], "error")

    return redirect(url_for("tickets_page"))
    if "user_id" not in session:
        return redirect(url_for("login"))

    if TicketController is None:
        return render_template("not_implemented.html", feature="Gestión de Tickets")

    result = TicketController.delete_ticket(ticket_id)

    if result["status"] == "success":
        flash("Ticket eliminado correctamente.", "success")
    else:
        flash(result["message"], "error")

    return redirect(url_for("tickets_page"))

@app.route('/api/tickets/audio', methods=['POST'])
@measure_submission('voice')
def crear_ticket_audio():
    if 'audio' not in request.files:
        return jsonify({"status": "error", "message": "Archivo de audio requerido"}), 400
    
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "ID de usuario requerido"}), 400

    file_stream = request.files['audio']
    resultado = TicketController.create_ticket_from_audio(file_stream, user_id)
    return jsonify(resultado), 201 if resultado["status"] == "success" else 400

from gtts import gTTS


@app.route('/api/tickets/voz', methods=['POST'])
@measure_submission('voice')
def generar_ticket_por_voz():
    audio = request.files.get('audio')
    if not audio or not allowed_file(audio.filename):
        return jsonify(error='Envia un archivo de audio permitido.'), 400
    result = TicketController.create_ticket_from_audio(audio, session['user_id'])
    if result['status'] != 'success':
        return jsonify(error=result['message']), 400
    return jsonify(mensaje='Reporte creado correctamente', ticket_id=result['id']), 201


@app.route("/chatbot")
def chatbot_view():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("chatbot.html")


@app.route("/monitoring")
def monitoring_page():
    if not can_monitor():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    if MonitoringController is None:
        return render_template("not_implemented.html", feature="Monitoreo")

    selected_name = request.args.get("name", "")
    db = Database()
    metric_names = [row["metric_name"] for row in db.execute_query("SELECT DISTINCT metric_name FROM monitoring_data ORDER BY metric_name")]
    query = "SELECT m.*, a.name AS asset_name FROM monitoring_data m JOIN assets a ON a.id=m.asset_id"
    params = ()
    if selected_name:
        query += " WHERE m.metric_name=%s"
        params = (selected_name,)
    metrics = db.execute_query(query + " ORDER BY m.timestamp DESC LIMIT 200", params)
    return render_template("monitoring/index.html", metrics=metrics, metric_names=metric_names, selected_name=selected_name)


@app.route("/monitoring/add", methods=["GET", "POST"])
def add_monitoring_metric():
    if not can_monitor():
        return deny_access()
    if "user_id" not in session:
        return redirect(url_for("login"))

    if MonitoringController is None:
        return render_template("not_implemented.html", feature="Monitoreo")

    if request.method == "POST":
        metric_data = {
            "asset_id": request.form.get("asset_id", type=int),
            "metric_name": request.form.get("name"),
            "metric_value": request.form.get("value"),
        }

        result = MonitoringController.add_metric(metric_data)

        if result["status"] == "success":
            flash("Métrica agregada correctamente.", "success")
            return redirect(url_for("monitoring_page"))
        else:
            flash(result["message"], "error")

    return render_template("monitoring/add.html", assets=AssetController.get_all_assets().get("data", []))


# RUTAS DE GESTIÓN DE USUARIOS

@app.route("/users")
def list_users():
    if not can_manage_users():
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("dashboard"))

    result = UserController.get_all_users()
    users = Database().execute_query("SELECT u.id,u.name,u.email,u.role,u.is_active,u.area_id,a.name AS area_name FROM users u LEFT JOIN areas a ON a.id=u.area_id ORDER BY u.name")

    return render_template("users/index.html", users=users)


@app.route("/users/create", methods=["GET", "POST"])
def create_user():
    if not can_manage_users():
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role", "user")

        result = UserController.create_user({
            "name": name,
            "email": email,
            "password": password,
            "role": role,
            "area_id": request.form.get('area_id', type=int)
        })

        if result["status"] == "success":
            flash("Usuario creado correctamente.", "success")
            return redirect(url_for("list_users"))
        else:
            flash(result["message"], "danger")

    return render_template("users/create.html")


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
def edit_user(user_id):
    if not can_manage_users():
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("dashboard"))

    result = UserController.get_user(user_id)
    if result["status"] != "success":
        flash("Usuario no encontrado.", "warning")
        return redirect(url_for("list_users"))

    user = result["data"]

    if request.method == "POST":
        updated_data = {
            "name": request.form.get("name"),
            "email": request.form.get("email"),
            "role": request.form.get("role"),
            "area_id": request.form.get('area_id', type=int),
            "is_active": True if request.form.get("is_active") else False
        }
        password = request.form.get("password")
        if password:
            updated_data["password"] = password

        update_result = UserController.update_user(user_id, updated_data)
        if update_result["status"] == "success":
            flash("Usuario actualizado correctamente.", "success")
            return redirect(url_for("list_users"))
        else:
            flash(update_result["message"], "danger")

    return render_template("users/edit.html", user=user)


@app.route("/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):
    if not can_manage_users():
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("dashboard"))

    result = UserController.delete_user(user_id)
    if result["status"] == "success":
        flash("Usuario eliminado correctamente.", "success")
    else:
        flash(result["message"], "danger")

    return redirect(url_for("list_users"))


@app.route("/users/<int:user_id>/toggle", methods=["POST"])
def toggle_user_active(user_id):
    if not can_manage_users():
        flash("No tienes permisos para esta acción.", "danger")
        return redirect(url_for("dashboard"))

    result = UserController.get_user(user_id)
    if result["status"] != "success":
        flash("Usuario no encontrado.", "warning")
        return redirect(url_for("list_users"))

    user = result["data"]
    updated_data = {"is_active": not user.get("is_active", True)}
    update_result = UserController.update_user(user_id, updated_data)

    if update_result["status"] == "success":
        flash("Estado del usuario actualizado.", "success")
    else:
        flash(update_result["message"], "danger")

    return redirect(url_for("list_users"))



@app.route("/profile")
def profile():
    from models.asset import Asset
    from models.ticket import Ticket
    user_id = session["user_id"]
    return render_template("profile.html", user=UserController.get_user(user_id).get("data", {}), recent_tickets=Ticket.find_by_created_user(user_id) if hasattr(Ticket, "find_by_created_user") else [], assigned_assets=Asset.find_by_assigned_user(user_id))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not can_manage_users():
        return redirect(url_for("dashboard"))
    from dotenv import set_key
    if request.method == "POST":
        if os.getenv('VERCEL'):
            flash('La configuración del servidor se administra en las variables de entorno de Vercel.', 'info')
            return redirect(url_for('settings'))
        fields = {"app_name": "APP_NAME", "email_notifications": "EMAIL_NOTIFICATIONS", "monitoring_interval": "MONITORING_INTERVAL", "mail_server": "MAIL_SERVER", "mail_port": "MAIL_PORT", "mail_username": "MAIL_USERNAME", "mail_password": "MAIL_PASSWORD", "mail_sender": "MAIL_DEFAULT_SENDER"}
        for field, key in fields.items():
            value = request.form.get(field)
            if value is not None and (field != "mail_password" or value):
                if field in ("monitoring_interval", "mail_port") and (not value.isdigit() or int(value) <= 0):
                    flash("Introduce un numero positivo", "error")
                    return redirect(url_for("settings"))
                set_key(os.path.join(BASE_DIR, ".env"), key, value)
                os.environ[key] = value
        flash("Configuracion guardada", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", config=os.environ)


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.route('/healthz')
def healthz():
    try:
        Database().execute_query('SELECT 1 AS ready')
        return jsonify(status='ok'), 200
    except Exception:
        return jsonify(status='unavailable'), 503


@app.errorhandler(413)
def file_too_large(error):
    if request.path.startswith('/api/'):
        return jsonify(error='El audio supera el límite de 4 MB. Graba un reporte más breve.'), 413
    flash('El archivo supera el límite de 4 MB.', 'warning')
    return redirect(url_for('chatbot_view'))


@app.errorhandler(404)
def page_not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("errors/500.html"), 500


#######################
# EJECUCIÓN
#######################

if __name__ == "__main__":
    # Información de inicio
    print(
        f"Iniciando {os.getenv('APP_NAME', 'Sistema de Gestión TI')} v{os.getenv('APP_VERSION', '1.0.0')}"
    )
    print(
        f"Servidor: {os.getenv('FLASK_HOST', '127.0.0.1')}:{os.getenv('FLASK_PORT', 5000)}"
    )
    print(f"Modo debug: {os.getenv('FLASK_DEBUG', 'False')}")

    # Verificar si la base de datos está configurada
    if Database is not None:
        try:
            db = Database()
            conn = db.get_connection()
            print("Conexión a la base de datos establecida correctamente")
            conn.close()
        except Exception as e:
            print(f"Error al conectar con la base de datos: {e}")
            print("La aplicación funcionará en modo limitado")
    else:
        print(
            "Módulo de base de datos no disponible. La aplicación funcionará en modo limitado."
        )

    # Iniciar aplicación
    app.run(
        debug=os.getenv("FLASK_DEBUG", "False") == "True",
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", 5000)),
    )
