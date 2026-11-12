from flask import session

ROLE_LABELS = {
    "super_admin": "Superadministrador",
    "admin": "Trabajador (rol anterior)",
    "manager": "Encargado de área",
    "technician": "Trabajador",
    "user": "Trabajador",
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
    return is_ti() and current_role() == 'manager'

def can_work_tickets():
    return is_ti() and current_role() != 'super_admin'

def can_edit_ticket(ticket):
    if not can_work_tickets() or ticket.get('status') in ('resolved','closed'):
        return False
    return ticket.get('destination_area_id') == session.get('area_id') and (
        current_role() == 'manager' or ticket.get('assigned_to') == session.get('user_id'))

def can_delete_tickets():
    return current_role() == "super_admin"

def can_monitor():
    return is_super_admin() or (is_ti() and current_role() in ("admin", "manager", "technician"))

def owns_ticket(ticket):
    return ticket.get("created_by") == session.get("user_id")

def can_see_ticket(ticket):
    if is_super_admin():
        return True
    area = session.get('area_id')
    if current_role() == 'manager' and area:
        return area in (ticket.get('origin_area_id'), ticket.get('destination_area_id'))
    return owns_ticket(ticket) or (bool(area) and ticket.get('destination_area_id') == area and ticket.get('assigned_to') == session.get('user_id'))

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
        "can_edit_ticket": can_edit_ticket,
        "can_delete_tickets": can_delete_tickets(),
        "can_monitor": can_monitor(),
    }


def is_super_admin():
    return current_role() == "super_admin"


def is_ti():
    return session.get("area_code") == "TI"
