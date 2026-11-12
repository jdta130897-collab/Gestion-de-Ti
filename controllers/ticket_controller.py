from models.ticket import Ticket
from utils.validators import validate_ticket
from datetime import datetime
from services.voice_service import VoiceService
from flask import request, jsonify, has_request_context, session, g
from services.ticket_service import TicketService
from flask import Blueprint, request, jsonify
from config.database import Database
import os
from services.notification_service import NotificationService


def notify(ticket_id, kind, message):
    try:
        NotificationService.emit(ticket_id, kind, message)
    except Exception:
        import logging
        logging.exception('No se pudo registrar la notificación del reporte %s', ticket_id)

voice_service = VoiceService()
ticket_service = TicketService()
ticket_bp = Blueprint("ticket_bp", __name__)

class TicketController:
    """Controlador para gestionar tickets de soporte."""

    @staticmethod
    def get_all_tickets(date_filter=None, priority_filter=None):
        try:
            tickets = Ticket.get_all_with_details(date_filter, priority_filter)
            if has_request_context() and session.get('user_id'):
                from utils.permissions import can_see_ticket
                tickets = [ticket for ticket in tickets if can_see_ticket(ticket)]
            if not tickets:
                return {"status": "success", "data": []}

            # Ordenar los reportes por fecha de creación (created_at), de más reciente a más antiguo
            tickets = sorted(tickets, key=lambda x: x["created_at"], reverse=True)
            return {"status": "success", "data": tickets}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def create_ticket_from_audio(file_stream, user_id):
        """Crea un ticket a partir de un archivo de audio utilizando IA de voz."""
        try:
            # 1. Guardar audio temporal
            temp_audio = voice_service.save_temp_audio(file_stream)

            try:
                # 2. Transcribir audio a texto
                texto = voice_service.transcribe_audio(temp_audio)

                # 3. Analizar texto para prioridad y categoría
                priority = "low"
                category = "general"
                texto_lower = texto.lower()

                if "urgente" in texto_lower or "crítico" in texto_lower:
                    priority = "critical"
                elif "importante" in texto_lower or "rápido" in texto_lower:
                    priority = "high"
                elif "normal" in texto_lower:
                    priority = "medium"

                if "impresora" in texto_lower:
                    category = "impresora"
                elif "red" in texto_lower or "wifi" in texto_lower:
                    category = "red"
                elif "software" in texto_lower or "programa" in texto_lower:
                    category = "software"

                # 4. Crear datos del reporte
                ticket_data = {
                    "title": texto[:60] + "...",
                    "description": f"{texto}\n\nCategoría: {category}",
                    "priority": priority,
                    "created_by": user_id,
                    "assigned_to": None,
                    "related_asset": None,
                    "initial_comment": "Creado desde transcripción de voz",
                    "channel": "voice",
                    "request_kind": request.form.get('request_kind', 'incident') if has_request_context() else 'incident',
                    "origin_area_id": request.form.get('origin_area_id', type=int) if has_request_context() else None,
                }

                return TicketController.create_ticket(ticket_data)
            finally:
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)

        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def create_ticket(ticket_data):
        try:
            from services.area_service import AreaService
            creator = AreaService.user_scope(ticket_data.get('created_by'))
            if not creator or not creator['is_active'] or not creator['area_active']:
                raise ValueError('El solicitante debe pertenecer a un área activa.')
            origin = creator['area_id']
            if has_request_context() and session.get('user_id'):
                if ticket_data.get('created_by') != session['user_id']:
                    raise ValueError('El solicitante debe ser el usuario autenticado.')
                if creator['role'] == 'super_admin' and ticket_data.get('origin_area_id'):
                    origin = int(ticket_data['origin_area_id'])
            area = AreaService.get(origin)
            if not area or not area['is_active']:
                raise ValueError('El área solicitante no está activa.')
            kind = ticket_data.get('request_kind', 'incident')
            channel = ticket_data.get('channel', 'manual')
            if kind not in ('incident', 'request') or channel not in ('manual', 'voice'):
                raise ValueError('Tipo de solicitud o canal no válido.')
            validation = validate_ticket(ticket_data)
            if not validation["valid"]:
                return {"status": "error", "message": validation["errors"]}

            ticket = Ticket(
                title=ticket_data.get("title"),
                description=ticket_data.get("description"),
                status="open",
                priority=ticket_data.get("priority"),
                created_by=ticket_data.get("created_by"),
                assigned_to=ticket_data.get("assigned_to"),
                related_asset=ticket_data.get("related_asset"),
                origin_area_id=origin, destination_area_id=AreaService.ti_id(),
                request_kind=kind, channel=channel,
            )

            ticket_id = ticket.save()

            initial_comment = ticket_data.get("initial_comment")
            if initial_comment and ticket_id:
                ticket.add_comment(ticket_data.get("created_by"), initial_comment)

            if has_request_context():
                g.created_ticket_id = ticket_id
            notify(ticket_id, 'created', f'Nuevo {"pedido" if kind == "request" else "reporte"} #{ticket_id} de {area["name"]}.')

            return {
                "status": "success",
                "message": "Reporte creado correctamente",
                "id": ticket_id,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_ticket(ticket_id):
        try:
            ticket = Ticket.get_ticket_with_details(ticket_id)
            if not ticket:
                return {"status": "error", "message": "Reporte no encontrado"}

            comments = Ticket.get_comments(ticket_id)
            if has_request_context() and session.get('user_id'):
                from utils.permissions import can_see_ticket
                if not can_see_ticket(ticket):
                    return {'status': 'error', 'message': 'No tienes acceso a este reporte.'}
            result = {"ticket": ticket, "comments": comments}
            return {"status": "success", "data": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def update_ticket(ticket_id, ticket_data):
        try:
            if has_request_context() and session.get('user_id'):
                from utils.permissions import can_work_tickets, can_assign_tickets
                if not can_work_tickets():
                    raise ValueError('Solo el equipo de TI puede atender los reportes.')
                if 'assigned_to' in ticket_data and not can_assign_tickets():
                    raise ValueError('No tienes permiso para asignar responsables.')
            if ticket_data.get('assigned_to'):
                from services.area_service import AreaService
                assignee = AreaService.user_scope(ticket_data['assigned_to'])
                if not assignee or not assignee['is_active'] or assignee['area_code'] != 'TI' or assignee['role'] not in ('admin', 'manager', 'technician'):
                    raise ValueError('Asigna el reporte a un integrante activo del equipo de TI.')
            validation = validate_ticket(ticket_data, update=True)
            if not validation["valid"]:
                return {"status": "error", "message": validation["errors"]}

            ticket = Ticket.get_by_id(ticket_id)
            if not ticket:
                return {"status": "error", "message": "Reporte no encontrado"}

            ticket.title = ticket_data.get("title", ticket.title)
            ticket.description = ticket_data.get("description", ticket.description)
            ticket.priority = ticket_data.get("priority", ticket.priority)
            previous_status = ticket.status
            previous_assignee = ticket.assigned_to
            ticket.status = ticket_data.get("status", ticket.status)
            ticket.resolved_at = datetime.now() if ticket.status in ('resolved', 'closed') else None
            ticket.assigned_to = ticket_data.get("assigned_to", ticket.assigned_to)
            ticket.related_asset = ticket_data.get("related_asset", ticket.related_asset)
            ticket.updated_by = ticket_data.get("updated_by")
            ticket.updated_at = datetime.now()

            ticket.save()

            if previous_status != ticket.status and ticket_data.get('updated_by'):
                from utils.helpers import translate_ticket_status
                ticket.add_comment(ticket_data['updated_by'], f"Estado actualizado: {translate_ticket_status(previous_status)} → {translate_ticket_status(ticket.status)}")

            update_comment = ticket_data.get("update_comment")
            if update_comment:
                ticket.add_comment(ticket_data.get("updated_by"), update_comment)

            from utils.helpers import translate_ticket_status
            if previous_status != ticket.status:
                notify(ticket_id, 'status', f'Reporte #{ticket_id}: {translate_ticket_status(ticket.status)}.')
            if str(previous_assignee or '') != str(ticket.assigned_to or ''):
                notify(ticket_id, 'assigned', f'Se actualizó el responsable del reporte #{ticket_id}.')
            if update_comment:
                notify(ticket_id, 'comment', f'TI registró una respuesta en el reporte #{ticket_id}.')

            return {"status": "success", "message": "Reporte actualizado correctamente"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def add_comment(ticket_id, comment_data):
        try:
            ticket = Ticket.get_by_id(ticket_id)
            if not ticket:
                return {"status": "error", "message": "Reporte no encontrado"}

            user_id = comment_data.get("user_id")
            comment_text = comment_data.get("comment")

            if not user_id or not comment_text:
                return {"status": "error", "message": "Datos de comentario incompletos"}

            ticket.add_comment(user_id, comment_text)
            notify(ticket_id, 'comment', f'Nuevo comentario en el reporte #{ticket_id}.')
            return {"status": "success", "message": "Comentario agregado correctamente"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def delete_ticket(ticket_id):
        try:
            ticket = Ticket.get_by_id(ticket_id)
            if not ticket:
                return {"status": "error", "message": "Reporte no encontrado"}

            ticket.delete()
            return {"status": "success", "message": "Reporte eliminado correctamente"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@ticket_bp.route("/api/chatbot/ticket", methods=["POST"])
def crear_ticket_chatbot():
    data = request.get_json()
    descripcion = data.get("descripcion")
    usuario = data.get("usuario")
    prioridad = data.get("prioridad")

    if not descripcion or not usuario or not prioridad:
        return jsonify({"error": "Datos incompletos"}), 400

    # Usamos el pool de conexiones a través de la clase Database
    db = Database()
    query = """
        INSERT INTO tickets (titulo, descripcion, usuario, prioridad, estado)
        VALUES (%s, %s, %s, %s, %s)
    """
    params = (
        f"Ticket generado por voz - {usuario}",
        descripcion,
        usuario,
        prioridad,
        "pendiente",
    )

    try:
        db.execute_update(query, params)
        return jsonify({"mensaje": "Reporte creado correctamente"})
    except Exception as e:
        return jsonify({"error": f"Error al crear ticket: {str(e)}"}), 500
