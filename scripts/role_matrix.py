"""Comprueba el acceso real de cada rol contra las rutas y el HTML."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from config.database import Database
from controllers.ticket_controller import TicketController
from models.user import User

app.testing = True
client = app.test_client()
db = Database()
failures = []


def check(condition, label):
    if condition:
        print("OK", label)
    else:
        failures.append(label)
        print("FALLO", label)


def login(email, password):
    client.get("/logout")
    response = client.post("/login", data={"email": email, "password": password}, follow_redirects=False)
    check(response.status_code == 302 and response.location.endswith("/dashboard"), f"login {email}")


def status_of(path):
    return client.get(path, follow_redirects=False).status_code


def body(path):
    response = client.get(path, follow_redirects=False)
    check(response.status_code == 200, f"GET 200 {path}")
    return response.get_data(as_text=True)


accounts = [
    ("tecnico@example.com", "tecnico123", "Tecnico Demo", "technician"),
    ("gerente@example.com", "gerente123", "Gerente Demo", "manager"),
    ("usuario@example.com", "usuario123", "Usuario Demo", "user"),
]
ids = {}
for email, password, name, role in accounts:
    found = User.find_by_email(email)
    if found:
        person = User(id=found["id"], name=name, email=email, role=role, password_hash=found["password_hash"])
        person.set_password(password)
        person.role = role
        person.save()
        ids[role] = found["id"]
    else:
        person = User(name=name, email=email, password=password, role=role)
        ids[role] = person.save()

admin = User.find_by_email("admin@example.com")
asset = db.execute_query("SELECT id FROM assets ORDER BY id LIMIT 1")
asset_id = asset[0]["id"] if asset else None

own = TicketController.create_ticket({
    "title": "Reporte solo del usuario demo",
    "description": "Visible unicamente para su autor y el equipo",
    "priority": "low",
    "status": "open",
    "created_by": ids["user"],
})
staff = TicketController.create_ticket({
    "title": "Incidente interno del equipo",
    "description": "No debe aparecer en la bandeja del usuario",
    "priority": "high",
    "status": "open",
    "created_by": admin["id"],
})
own_id = own.get("id")
staff_id = staff.get("id")

try:
    login("usuario@example.com", "usuario123")
    page = body("/dashboard")
    for forbidden in ("/assets", "/monitoring", "/users", "/settings"):
        check(f'href="{forbidden}"' not in page and f"href='{forbidden}'" not in page, f"usuario sin enlace {forbidden}")
    check('href="/tickets"' in page, "usuario ve tickets")
    for path in ("/assets", "/assets/create", "/monitoring", "/monitoring/add", "/users", "/settings", f"/tickets/{staff_id}", f"/tickets/{own_id}/edit"):
        check(status_of(path) == 302, f"usuario bloqueado {path}")
    check(status_of(f"/tickets/{own_id}") == 200, "usuario abre su ticket")
    listing = body("/tickets")
    check("Reporte solo del usuario demo" in listing, "usuario ve su ticket")
    check("Incidente interno del equipo" not in listing, "usuario no ve tickets ajenos")
    check("/edit" not in listing, "usuario no ve editar")
    created = client.post("/tickets/create", data={
        "subject": "Reporte forzado a abierto",
        "description": "El usuario no elige el estado",
        "priority": "low",
        "status": "closed",
    }, follow_redirects=False)
    check(created.status_code == 302, "usuario crea ticket")
    forced = db.execute_query("SELECT id, status FROM tickets WHERE title=%s ORDER BY id DESC LIMIT 1", ("Reporte forzado a abierto",))
    check(forced and forced[0]["status"] == "open", "ticket de usuario queda abierto")
    if forced:
        TicketController.delete_ticket(forced[0]["id"])

    login("tecnico@example.com", "tecnico123")
    page = body("/dashboard")
    check('href="/assets"' in page and 'href="/monitoring"' in page, "tecnico ve activos y monitoreo")
    check('href="/users"' not in page and 'href="/settings"' not in page, "tecnico sin usuarios ni ajustes")
    assets_html = body("/assets")
    check("Nuevo Activo" not in assets_html and "/edit" not in assets_html, "tecnico solo consulta activos")
    check(status_of("/assets/create") == 302, "tecnico no crea activos")
    if asset_id:
        check(status_of(f"/assets/{asset_id}") == 200, "tecnico abre un activo")
        check(status_of(f"/assets/{asset_id}/edit") == 302, "tecnico no edita activos")
    check(status_of("/monitoring") == 200 and status_of("/users") == 302 and status_of("/settings") == 302, "tecnico monitoreo si, sistema no")
    editor = body(f"/tickets/{staff_id}/edit")
    check('name="assigned_to"' not in editor, "tecnico no asigna tickets")
    deleted = client.post(f"/tickets/{staff_id}/delete", follow_redirects=False)
    check(deleted.status_code == 302 and deleted.location.endswith("/dashboard"), "tecnico no elimina tickets")
    still = db.execute_query("SELECT id FROM tickets WHERE id=%s", (staff_id,))
    check(bool(still), "ticket sigue existiendo")

    login("gerente@example.com", "gerente123")
    page = body("/dashboard")
    check('href="/users"' not in page and 'href="/settings"' not in page, "gerente sin usuarios ni ajustes")
    check(status_of("/assets/create") == 200, "gerente crea activos")
    check(status_of("/users") == 302 and status_of("/settings") == 302, "gerente bloqueado en sistema")
    editor = body(f"/tickets/{staff_id}/edit")
    check('name="assigned_to"' in editor, "gerente asigna tickets")
    deleted = client.post(f"/tickets/{staff_id}/delete", follow_redirects=False)
    check(deleted.status_code == 302 and deleted.location.endswith("/dashboard"), "gerente no elimina tickets")

    login("admin@example.com", "admin123")
    for path in ("/dashboard", "/assets", "/assets/create", "/tickets", "/monitoring", "/users", "/settings", "/profile"):
        check(status_of(path) == 200, f"admin {path}")
    detail = body(f"/tickets/{staff_id}")
    check("Eliminar" in detail, "admin elimina tickets")
    editor = body(f"/tickets/{staff_id}/edit")
    check('name="assigned_to"' in editor, "admin asigna tickets")
finally:
    if own_id:
        TicketController.delete_ticket(own_id)
    if staff_id:
        TicketController.delete_ticket(staff_id)

print("FALLOS", len(failures))
for item in failures:
    print("-", item)
sys.exit(1 if failures else 0)
