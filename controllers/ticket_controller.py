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
from services.audio_archive import AudioArchive


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
        recording_id = None
        try:
            if not has_request_context() or request.form.get('retain_audio') != '1':
                raise ValueError('Autoriza la conservación privada del audio antes de grabar.')
            # 1. Guardar audio temporal
            temp_audio = voice_service.save_temp_audio(file_stream)

            try:
                recording_id = AudioArchive.save(temp_audio,user_id,getattr(g,'measurement_attempt_id',None))
                # 2. Transcribir audio a texto
                texto = voice_service.transcribe_audio(temp_audio)
                if not texto or not texto.strip():
                    raise ValueError('No se detectó una descripción en el audio. Intenta hablar de nuevo.')

                classification = voice_service.classify_ticket(texto)
                priority = classification['priority']
                category = classification['category']
                # 4. Crear datos del reporte
                ticket_data = {
                    "title": texto[:60] + "...",
                    "description": f"{texto}\n\nCategoría: {category}",
                    "priority": priority,
                    "created_by": user_id,
                    "assigned_to": None,
                    "related_asset": None,
                    "initial_comment": "Clasificado por voz (AssemblyAI LLM Gateway, " + os.getenv("ASSEMBLYAI_CLASSIFIER_MODEL", "qwen3.5-4b-32k-fast") + "): " + classification["reason"],
                    "channel": "voice",
                    "request_kind": classification['request_kind'],
                    "origin_area_id": request.form.get('origin_area_id', type=int) if has_request_context() else None,
                }

                result = TicketController.create_ticket(ticket_data)
                AudioArchive.finish(recording_id,ticket_id=result.get('id'),transcript=texto,
                    error_code=None if result.get('id') else 'ticket_validation_failed')
                return result
            finally:
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)

        except Exception as e:
            if recording_id:
                AudioArchive.finish(recording_id,error_code=type(e).__name__)
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
            if ticket_data.get('assigned_to'):
                raise ValueError('Crea el ticket sin responsable; el encargado del área de destino debe asignarlo.')
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
            original = Ticket.get_ticket_with_details(ticket_id)
            if not original:
                raise ValueError('Reporte no encontrado.')
            if original['status'] in ('resolved', 'closed'):
                raise ValueError('Un ticket resuelto o cerrado no puede editarse.')
            if has_request_context():
                from services.area_service import AreaService
                actor = AreaService.user_scope(session.get('user_id'))
                if not actor or not actor['is_active'] or not actor['area_active']:
                    raise ValueError('Usuario no autorizado.')
                in_area = actor['area_code'] == 'TI' and actor['area_id'] == original['destination_area_id']
                manager = in_area and actor['role'] == 'manager'
                worker = in_area and str(original.get('assigned_to')) == str(actor['id'])
                if not (manager or worker):
                    raise ValueError('Solo el encargado del área de destino o el trabajador asignado puede atender este ticket.')
                changed_assignment = 'assigned_to' in ticket_data and str(ticket_data['assigned_to'] or '') != str(original.get('assigned_to') or '')
                if changed_assignment and not manager:
                    raise ValueError('Solo el encargado del área de destino puede asignar responsables.')
                ticket_data['updated_by'] = actor['id']
            locked = original.get('classification_locked') or original.get('assigned_to')
            for field in ('priority', 'request_kind'):
                if field in ticket_data and ticket_data[field] != original[field] and locked:
                    raise ValueError('La prioridad y el tipo quedan bloqueados desde la primera asignación.')
            if ticket_data.get('assigned_to'):
                from services.area_service import AreaService
                assignee = AreaService.user_scope(ticket_data['assigned_to'])
                if not assignee or not assignee['is_active'] or not assignee['area_active'] or assignee['area_id'] != original['destination_area_id'] or assignee['role'] == 'super_admin':
                    raise ValueError('El responsable debe ser un trabajador activo del área de destino.')
            if ticket_data.get('status') in ('resolved','closed') and not (ticket_data.get('update_comment') or '').strip():
                raise ValueError('Registra la solución antes de resolver o cerrar el ticket.')
            validation = validate_ticket(ticket_data, update=True)
            if not validation['valid']:
                return {'status':'error','message':validation['errors']}
            ticket = Ticket.get_by_id(ticket_id)
            ticket.request_kind = ticket_data.get('request_kind', ticket.request_kind)
            if ticket.request_kind not in ('incident','request'):
                raise ValueError('Tipo de solicitud no válido.')
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

            if ticket.status in ('resolved','closed'):
                raise ValueError('Un ticket resuelto o cerrado no admite modificaciones ni comentarios.')
            if has_request_context():
                from services.area_service import AreaService
                actor = AreaService.user_scope(session.get('user_id'))
                allowed = actor and actor['is_active'] and actor['area_active'] and actor['area_code'] == 'TI' and actor['area_id'] == ticket.destination_area_id and (actor['role'] == 'manager' or actor['id'] == ticket.assigned_to)
                if not allowed or comment_data.get('user_id') != session.get('user_id'):
                    raise ValueError('Solo TI puede registrar el seguimiento del ticket.')
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
