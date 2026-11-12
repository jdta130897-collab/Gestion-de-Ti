"""Prueba contra MySQL con usuarios y áreas temporales; voz simulada sin llamadas externas."""
import io
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from config.database import Database
from models.user import User
from controllers.ticket_controller import TicketController
from controllers.user_controller import UserController
from services.area_service import AreaService
from scripts.migrate_areas import migrate

app.testing = True
db = Database()
tag = uuid.uuid4().hex[:8].upper()
password = uuid.uuid4().hex
users, areas, reports, results = [], [], [], []
baseline = {t: db.execute_query(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] for t in ('users', 'areas', 'tickets', 'ticket_comments')}


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    results.append(label)
    print('OK', label)


def person(role, area_id):
    user = User(name='Prueba ' + tag, email=uuid.uuid4().hex + '@example.invalid', password=password, role=role, area_id=area_id)
    users.append(user.save())
    client = app.test_client()
    response = client.post('/login', data={'email': user.email, 'password': password})
    check(response.status_code == 302 and response.location.endswith('/dashboard'), 'Autenticación ' + role)
    return user.id, client


def create(client, kind, title, **extra):
    response = client.post('/tickets/create', data={'subject': title, 'description': 'Descripción de verificación temporal.', 'priority': 'high', 'request_kind': kind, **extra})
    rows = db.execute_query('SELECT * FROM tickets WHERE title=%s', (title,))
    check(response.status_code == 302 and len(rows) == 1, 'Crear ' + kind)
    reports.append(rows[0]['id'])
    return rows[0]


try:
    ti = AreaService.ti_id()
    sid, super_client = person('super_admin', ti)
    for code in ('A' + tag, 'B' + tag):
        response = super_client.post('/areas', data={'code': code, 'name': 'Área temporal ' + code})
        rows = db.execute_query('SELECT * FROM areas WHERE code=%s', (code,))
        check(response.status_code == 302 and len(rows) == 1, 'Superadministrador crea área')
        areas.append(rows[0]['id'])
    a, b = areas
    super_client.post('/areas', data={'code': 'A' + tag, 'name': 'Duplicada ' + tag})
    check(len(db.execute_query('SELECT id FROM areas WHERE code=%s', ('A' + tag,))) == 1, 'Código de área único')
    super_client.post(f'/areas/{ti}/toggle')
    check(AreaService.get(ti)['is_active'], 'TI no se desactiva')
    manager_id, manager = person('manager', a)
    first_id, first = person('user', a)
    second_id, second = person('user', a)
    foreign_id, foreign = person('user', b)
    tech_id, tech = person('technician', ti)
    admin_id, admin = person('admin', ti)
    for client in (manager, first, foreign, tech, admin):
        check(client.get('/areas').status_code == 403, 'Solo superadministrador gestiona áreas')
        check(client.post('/areas', data={'code': 'NO', 'name': 'No permitido'}).status_code == 403, 'Crear área bloqueado en servidor')
        check(client.get('/users/create').status_code == 302, 'Solo superadministrador crea usuarios')
    for client in (manager, first, foreign):
        for path in ('/assets', '/monitoring'):
            check(client.get(path).status_code == 302, 'Área solicitante sin acceso a ' + path)
    for client in (tech, admin, super_client):
        check(client.get('/assets').status_code == 200, 'Equipo TI consulta inventario')
    with patch('services.email_service.EmailService.send_welcome_email', return_value=True):
        email = uuid.uuid4().hex + '@example.invalid'
        response = super_client.post('/users/create', data={'name': 'Usuario ' + tag, 'email': email, 'password': password, 'role': 'user', 'area_id': b})
        created = User.find_by_email(email)
        if created:
            users.append(created['id'])
        check(response.status_code == 302 and created and created['area_id'] == b, 'Asignación de usuario a otra área desde formulario')
        for role in ('admin', 'technician'):
            email = uuid.uuid4().hex + '@example.invalid'
            super_client.post('/users/create', data={'name': 'Inválido ' + tag, 'email': email, 'password': password, 'role': role, 'area_id': b})
            check(User.find_by_email(email) is None, 'Personal TI no se asigna a otra área')
    incident = create(first, 'incident', 'Incidencia ' + tag, origin_area_id=b, created_by=foreign_id, destination_area_id=b)
    check(incident['origin_area_id'] == a and incident['created_by'] == first_id and incident['destination_area_id'] == ti, 'Origen, solicitante y destino protegidos ante manipulación')
    order = create(second, 'request', 'Pedido ' + tag)
    outside = create(foreign, 'request', 'Otra area ' + tag)
    represented = create(super_client, 'request', 'Representado ' + tag, origin_area_id=b)
    check(represented['origin_area_id'] == b, 'Superadministrador registra pedido para un área')
    for client in (first, manager):
        check(client.get(f"/tickets/{outside['id']}?preview=1").status_code == 302, 'Bloqueo de vista previa entre áreas')
        response = client.post(f"/tickets/{incident['id']}/edit", data={'subject': 'No autorizado', 'status': 'closed'})
        check(response.status_code == 302 and TicketController.get_ticket(incident['id'])['data']['ticket']['status'] == 'open', 'Solicitante no atiende reportes')
    check(first.get(f"/tickets/{order['id']}").status_code == 302, 'Solicitante solo ve sus propios reportes')
    check(manager.get(f"/tickets/{order['id']}").status_code == 200, 'Responsable ve los pedidos de su área')
    html = manager.get('/tickets').get_data(as_text=True)
    check(order['title'] in html and outside['title'] not in html, 'Listado aislado por área')
    dashboard = first.get('/dashboard').get_data(as_text=True)
    check(outside['title'] not in dashboard and order['title'] not in dashboard, 'Panel respeta el alcance del solicitante')
    for client in (tech, admin, super_client):
        check(client.get(f"/tickets/{outside['id']}?preview=1").status_code == 200, 'TI y superadministrador reciben solicitudes de todas las áreas')
    update = {'subject': incident['title'], 'description': incident['description'], 'priority': 'high', 'status': 'in_progress', 'assigned_to': first_id}
    admin.post(f"/tickets/{incident['id']}/edit", data=update)
    check(TicketController.get_ticket(incident['id'])['data']['ticket']['assigned_to'] is None, 'Asignación a solicitantes rechazada')
    update['assigned_to'] = tech_id
    admin.post(f"/tickets/{incident['id']}/edit", data=update)
    saved = TicketController.get_ticket(incident['id'])['data']['ticket']
    check(saved['assigned_to'] == tech_id and saved['status'] == 'in_progress', 'Administrador TI asigna y toma en atención')
    update.pop('assigned_to')
    update.update(status='resolved', update_comment='Solución temporal comprobada por TI.')
    tech.post(f"/tickets/{incident['id']}/edit", data=update)
    detail = TicketController.get_ticket(incident['id'])['data']
    check(detail['ticket']['status'] == 'resolved' and detail['ticket']['resolved_at'], 'Técnico resuelve con fecha de atención')
    check(any('Solución temporal' in c['comment'] for c in detail['comments']), 'Respuesta TI visible en seguimiento')
    check('Solución temporal' in first.get(f"/tickets/{incident['id']}?preview=1").get_data(as_text=True), 'Solicitante consulta la respuesta de TI')
    update.update(status='closed', update_comment='Atención finalizada.')
    admin.post(f"/tickets/{incident['id']}/edit", data=update)
    check(TicketController.get_ticket(incident['id'])['data']['ticket']['status'] == 'closed', 'Cierre de atención')
    with patch('controllers.ticket_controller.voice_service.transcribe_audio', return_value='Solicito asistencia importante para configurar el equipo de mi área.'):
        for endpoint in ('/api/tickets/voz', '/api/tickets/audio'):
            response = foreign.post(endpoint, data={'retain_audio':'1','audio': (io.BytesIO(b'audio simulado'), 'prueba.wav'), 'request_kind': 'request', 'origin_area_id': a, 'user_id': first_id}, content_type='multipart/form-data')
            body = response.get_json()
            rid = body.get('ticket_id') or body.get('id')
            if rid:
                reports.append(rid)
            check(response.status_code == 201 and rid, 'Creación por voz simulada ' + endpoint)
            saved = TicketController.get_ticket(rid)['data']['ticket']
            check(saved['origin_area_id'] == b and saved['created_by'] == foreign_id and saved['destination_area_id'] == ti and saved['channel'] == 'voice' and saved['request_kind'] == 'request', 'Voz usa el mismo flujo y alcance que el formulario')
    super_client.post(f'/areas/{b}/toggle')
    check(foreign.get('/tickets').status_code == 403, 'Área desactivada bloquea sesiones existentes')
    check(super_client.get('/areas').status_code == 200, 'Superadministrador puede reactivar áreas')
    super_client.post(f'/areas/{b}/toggle')
    check(foreign.get('/tickets').status_code == 200, 'Reactivación conserva acceso e historial')
    db.execute_update("UPDATE users SET role='user' WHERE id=%s", (tech_id,))
    check(tech.get('/assets').status_code == 302, 'Cambios de rol se aplican a sesiones abiertas')
    for path in ('/areas', '/users', f'/users/{first_id}/edit', '/tickets/create', '/chatbot', '/profile', '/settings'):
        check(super_client.get(path).status_code == 200, 'Vista actualizada ' + path)
    before = {t: db.execute_query(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] for t in ('users', 'areas', 'tickets')}
    migrate()
    after = {t: db.execute_query(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] for t in ('users', 'areas', 'tickets')}
    check(before == after, 'Migración repetible sin duplicar ni perder registros')
finally:
    for rid in reports:
        TicketController.delete_ticket(rid)
    for uid in users:
        db.execute_update('DELETE FROM users WHERE id=%s', (uid,))
    for aid in areas:
        db.execute_update('DELETE FROM areas WHERE id=%s', (aid,))
    remaining = {t: db.execute_query(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] for t in baseline}
    check(remaining == baseline, 'Limpieza de fixtures y conservación de datos originales')
    Path('.runtime/area-workflow-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print('Comprobaciones completadas:', len(results))
