from flask import session

ROLE_LABELS = {
    "super_admin": "Superadministrador",
    "admin": "Administrador de TI",
    "manager": "Responsable de área",
    "technician": "Técnico de TI",
    "user": "Solicitante",
}

def current_role():
    return session.get("user_role") or "user"

def can_manage_users():
    return current_role() == "super_admin"

def can_manage_assets():
    return is_super_admin() or (is_ti() and current_role() in ("admin", "manager"))

def can_view_assets():
    return is_super_admin() or (is_ti() and current_role() in ("admin", "manager", "technician"))

def can_assign_tickets():
    return is_super_admin() or (is_ti() and current_role() in ("admin", "manager"))

def can_work_tickets():
    return is_super_admin() or (is_ti() and current_role() in ("admin", "manager", "technician"))

def can_delete_tickets():
    return current_role() == "super_admin"

def can_monitor():
    return is_super_admin() or (is_ti() and current_role() in ("admin", "manager", "technician"))

def owns_ticket(ticket):
    return ticket.get("created_by") == session.get("user_id")

def can_see_ticket(ticket):
    if can_work_tickets():
        return True
    if current_role() == "manager":
        return bool(session.get("area_id")) and ticket.get("origin_area_id") == session.get("area_id")
    return owns_ticket(ticket)

def as_template_context():
    role = current_role()
    return {
        "current_role": role,
        "can_manage_areas": is_super_admin(),
        "current_area_name": session.get("area_name", "Sin area"),
        "role_label": ROLE_LABELS.get(role, role),
        "can_manage_users": can_manage_users(),
        "can_manage_assets": can_manage_assets(),
        "can_view_assets": can_view_assets(),
        "can_assign_tickets": can_assign_tickets(),
        "can_work_tickets": can_work_tickets(),
        "can_delete_tickets": can_delete_tickets(),
        "can_monitor": can_monitor(),
    }


def is_super_admin():
    return current_role() == "super_admin"


def is_ti():
    return session.get("area_code") == "TI"
