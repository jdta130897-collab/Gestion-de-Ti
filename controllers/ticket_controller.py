from models.ticket import Ticket
from utils.validators import validate_ticket
from datetime import datetime
from time import perf_counter
from services.voice_service import VoiceService, ClassificationRejectedError
from flask import request, jsonify, has_request_context, session, g
from services.ticket_service import TicketService
from flask import Blueprint, request, jsonify
from config.database import Database
import os
from services.notification_service import NotificationService
from services.audio_archive import AudioArchive
from services.participant_service import ParticipantService
from services.classification_trace_service import ClassificationTraceService
from services.measurement_service import MeasurementService
from utils.release import get_evaluation_session_id, PROMPT_VERSION
from utils.timezone import utc_now


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
    def _build_snapshot_payload(ticket_data, participant, ticket_id=None, attempt_id=None, error_code=None):
        channel = ticket_data.get('channel', 'manual')
        cls_data = ticket_data.get('_classification')
        trace = ticket_data.get('_classifier_trace')
        if channel == 'manual':
            return {
                'attempt_id': attempt_id,
                'ticket_id': ticket_id,
                'recording_id': None,
                'user_id': ticket_data.get('created_by'),
                'participant_id': participant['id'],
                'participant_code': participant['code'],
                'channel': 'manual',
                'source_mode': 'manual_form',
                'validated_payload_json': {
                    'request_kind': ticket_data.get('request_kind', 'incident'),
                    'priority': ticket_data.get('priority'),
                },
                'initial_request_kind': ticket_data.get('request_kind', 'incident'),
                'initial_priority': ticket_data.get('priority'),
                'classification_status': 'manual_selected',
                'priority_source': 'manual_form',
                'is_provisional': False,
                'in_scope': True,
                'scope_reason': 'ok',
                'prompt_version': None,
                'error_code': error_code,
            }

        source_mode = 'llm_voice' if trace else ('voice_rejected' if error_code in ('out_of_scope', 'insufficient_context') else ('voice_error' if error_code else 'simulated_voice'))
        if error_code and not cls_data:
            raw_json = trace.get('raw_response_text') if trace else None
            parsed_json = trace.get('parsed_json') if trace else None
            return {
                'attempt_id': attempt_id,
                'ticket_id': None,
                'recording_id': ticket_data.get('recording_id'),
                'user_id': ticket_data.get('created_by'),
                'participant_id': participant['id'],
                'participant_code': participant['code'],
                'channel': 'voice',
                'source_mode': 'voice_rejected' if error_code in ('out_of_scope', 'insufficient_context') else 'voice_error',
                'transcript': ticket_data.get('transcript'),
                'raw_classifier_json': raw_json,
                'validated_payload_json': parsed_json,
                'initial_request_kind': parsed_json.get('request_kind') if isinstance(parsed_json, dict) else None,
                'initial_impact': parsed_json.get('impact') if isinstance(parsed_json, dict) else None,
                'initial_urgency': parsed_json.get('urgency') if isinstance(parsed_json, dict) else None,
                'initial_category': parsed_json.get('category') if isinstance(parsed_json, dict) else None,
                'initial_reason': parsed_json.get('reason') if isinstance(parsed_json, dict) else None,
                'classification_status': 'rejected' if error_code in ('out_of_scope', 'insufficient_context') else 'error',
                'priority_source': 'rejected' if error_code in ('out_of_scope', 'insufficient_context') else 'error',
                'is_provisional': False,
                'has_mixed_requests': parsed_json.get('has_mixed_requests') if isinstance(parsed_json, dict) else None,
                'in_scope': False if error_code in ('out_of_scope', 'insufficient_context') else None,
                'scope_reason': error_code if error_code in ('out_of_scope', 'insufficient_context') else None,
                'classifier_model': (trace or {}).get('classifier_model') or os.getenv('ASSEMBLYAI_CLASSIFIER_MODEL', 'qwen3.5-4b-32k-fast'),
                'classifier_config_json': (trace or {}).get('classifier_config'),
                'prompt_version': (trace or {}).get('prompt_version') or PROMPT_VERSION,
                'error_code': error_code,
            }

        cls_data = cls_data or {}
        impact = cls_data.get('impact', 'unknown')
        urgency = cls_data.get('urgency', 'unknown')
        cls_status = cls_data.get('classification_status') or (
            'provisional' if ('unknown' in (impact, urgency) and ('impact' in cls_data or 'urgency' in cls_data))
            else ('definitive' if impact in ('individual', 'area', 'organization') and urgency in ('routine', 'degraded', 'blocked') else 'simulated')
        )
        prio_source = cls_data.get('priority_source') or (
            'provisional_fallback' if cls_status == 'provisional'
            else ('matrix' if cls_status == 'definitive' else 'simulated')
        )
        return {
            'attempt_id': attempt_id,
            'ticket_id': ticket_id,
            'recording_id': ticket_data.get('recording_id'),
            'user_id': ticket_data.get('created_by'),
            'participant_id': participant['id'],
            'participant_code': participant['code'],
            'channel': 'voice',
            'source_mode': source_mode,
            'transcript': ticket_data.get('transcript'),
            'raw_classifier_json': (trace or {}).get('raw_response_text') or cls_data,
            'validated_payload_json': cls_data,
            'initial_request_kind': cls_data.get('request_kind') or ticket_data.get('request_kind'),
            'initial_impact': cls_data.get('impact'),
            'initial_urgency': cls_data.get('urgency'),
            'initial_category': cls_data.get('category'),
            'initial_reason': cls_data.get('reason'),
            'initial_priority': cls_data.get('priority') or ticket_data.get('priority'),
            'classification_status': cls_status,
            'priority_source': prio_source,
            'is_provisional': cls_status == 'provisional' or bool(cls_data.get('is_fallback')),
            'has_mixed_requests': cls_data.get('has_mixed_requests'),
            'in_scope': cls_data.get('in_scope', True),
            'scope_reason': cls_data.get('scope_reason', 'ok'),
            'classifier_model': (trace or {}).get('classifier_model') or os.getenv('ASSEMBLYAI_CLASSIFIER_MODEL', 'qwen3.5-4b-32k-fast'),
            'classifier_config_json': (trace or {}).get('classifier_config') or {'mode': 'simulated_or_patched'},
            'prompt_version': (trace or {}).get('prompt_version') or PROMPT_VERSION,
            'error_code': error_code,
        }

    @staticmethod
    def create_ticket_from_audio(file_stream, user_id):
        """Crea un ticket a partir de un archivo de audio utilizando IA de voz."""
        recording_id = None
        texto = None
        attempt_id = getattr(g, 'measurement_attempt_id', None) if has_request_context() else None
        voice_service.clear_last_trace()
        try:
            if not has_request_context() or request.form.get('retain_audio') != '1':
                raise ValueError('Autoriza la conservación privada del audio antes de grabar.')
            # 1. Guardar audio temporal
            temp_audio = voice_service.save_temp_audio(file_stream)

            try:
                recording_id = AudioArchive.save(temp_audio, user_id, attempt_id)
                # 2. Transcribir audio a texto
                texto = voice_service.transcribe_audio(temp_audio)
                if not texto or not texto.strip():
                    raise ValueError('No se detectó una descripción en el audio. Intenta hablar de nuevo.')

                voice_service.clear_last_trace()
                classification = voice_service.classify_ticket(texto)
                trace = voice_service.get_last_trace()
                priority = classification['priority']
                category = classification['category']
                impact = classification.get('impact', 'unknown')
                urgency = classification.get('urgency', 'unknown')
                has_mixed = bool(classification.get('has_mixed_requests', False))
                classification_status = classification.get('classification_status')
                if not classification_status:
                    if impact in ('individual', 'area', 'organization') and urgency in ('routine', 'degraded', 'blocked'):
                        classification_status = 'definitive'
                    elif 'unknown' in (impact, urgency) and ('impact' in classification or 'urgency' in classification):
                        classification_status = 'provisional'
                    else:
                        classification_status = 'provisional' if classification.get('is_fallback') else 'unverified'
                priority_source = classification.get('priority_source') or (
                    'provisional_fallback' if classification_status == 'provisional'
                    else ('matrix' if classification_status == 'definitive' else 'external_or_mock')
                )
                model_name = os.getenv("ASSEMBLYAI_CLASSIFIER_MODEL", "qwen3.5-4b-32k-fast")
                status_label = (
                    "PROVISIONAL (prioridad media de respaldo por información incompleta; no es predicción validada; revisar antes de asignar)"
                    if classification_status == "provisional"
                    else (
                        "Definitiva (matriz impacto x urgencia)"
                        if classification_status == "definitive"
                        else "No verificada / externa"
                    )
                )
                mixed_label = " | Solicitudes múltiples detectadas (revisar posible desglose)" if has_mixed else ""
                initial_comment = (
                    f"Clasificado por voz (AssemblyAI LLM Gateway, {model_name}) "
                    f"[{status_label} | tipo={classification['request_kind']} | impacto={impact} | "
                    f"urgencia={urgency} | origen_prioridad={priority_source}{mixed_label}]: "
                    f"{classification['reason']}"
                )
                # 4. Crear datos del reporte
                ticket_data = {
                    "title": texto[:60] + "...",
                    "description": f"{texto}\n\nCategoría: {category}",
                    "priority": priority,
                    "created_by": user_id,
                    "assigned_to": None,
                    "related_asset": None,
                    "initial_comment": initial_comment,
                    "channel": "voice",
                    "request_kind": classification['request_kind'],
                    "origin_area_id": request.form.get('origin_area_id', type=int) if has_request_context() else None,
                    "attempt_id": attempt_id,
                    "recording_id": recording_id,
                    "transcript": texto,
                    "_classification": classification,
                    "_classifier_trace": trace,
                }

                result = TicketController.create_ticket(ticket_data)
                if result.get('status') == 'success':
                    result['classification_status'] = classification_status
                    result['priority_source'] = priority_source
                    result['has_mixed_requests'] = has_mixed
                    result['request_kind'] = classification['request_kind']
                    result['priority'] = priority
                else:
                    if has_request_context():
                        g.measurement_error_reason = 'ticket_validation_failed'
                    AudioArchive.finish(recording_id, ticket_id=None, transcript=texto, error_code='ticket_validation_failed')
                    try:
                        participant = ParticipantService.ensure_for_user(user_id)
                        snap = TicketController._build_snapshot_payload(ticket_data, participant, ticket_id=None, attempt_id=attempt_id, error_code='ticket_validation_failed')
                        ClassificationTraceService.save_snapshot(snap)
                    except Exception:
                        pass
                return result
            finally:
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)

        except Exception as e:
            err_code = getattr(e, 'error_code', type(e).__name__)
            if has_request_context():
                g.measurement_error_reason = err_code
            if recording_id:
                AudioArchive.finish(recording_id, transcript=texto, error_code=err_code)
            if user_id and (recording_id or texto):
                try:
                    participant = ParticipantService.ensure_for_user(user_id)
                    snap = TicketController._build_snapshot_payload(
                        {
                            'created_by': user_id,
                            'channel': 'voice',
                            'recording_id': recording_id,
                            'transcript': texto,
                            '_classifier_trace': voice_service.get_last_trace(),
                        },
                        participant,
                        ticket_id=None,
                        attempt_id=attempt_id,
                        error_code=err_code,
                    )
                    ClassificationTraceService.save_snapshot(snap)
                except Exception:
                    pass
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
                if has_request_context():
                    g.measurement_error_reason = 'ticket_validation_failed'
                return {"status": "error", "message": validation["errors"]}

            attempt_id = ticket_data.get('attempt_id') or (getattr(g, 'measurement_attempt_id', None) if has_request_context() else None)
            recording_id = ticket_data.get('recording_id')
            transcript = ticket_data.get('transcript')
            eval_session = ticket_data.get('evaluation_session_id') if 'evaluation_session_id' in ticket_data else get_evaluation_session_id()
            dest_area_id = AreaService.ti_id()

            db = Database()
            ticket_id = None
            total_ms = None
            already_persisted = False

            with db.transaction() as tx:
                participant = ParticipantService.ensure_for_user(ticket_data.get('created_by'), tx=tx)
                if attempt_id:
                    existing = tx.query(
                        'SELECT outcome, ticket_id, evaluation_session_id FROM creation_attempts WHERE id=%s AND user_id=%s FOR UPDATE',
                        (attempt_id, ticket_data.get('created_by')),
                    )
                    if existing:
                        if eval_session is None and existing[0].get('evaluation_session_id'):
                            eval_session = existing[0]['evaluation_session_id']
                            ticket_data['evaluation_session_id'] = eval_session
                        if existing[0]['outcome'] == 'success' and existing[0]['ticket_id']:
                            ticket_id = existing[0]['ticket_id']
                            already_persisted = True

                if not already_persisted:
                    ticket = Ticket(
                        title=ticket_data.get("title"),
                        description=ticket_data.get("description"),
                        status="open",
                        priority=ticket_data.get("priority"),
                        created_by=ticket_data.get("created_by"),
                        assigned_to=ticket_data.get("assigned_to"),
                        related_asset=ticket_data.get("related_asset"),
                        origin_area_id=origin,
                        destination_area_id=dest_area_id,
                        request_kind=kind,
                        channel=channel,
                        attempt_id=attempt_id,
                        evaluation_session_id=eval_session,
                    )
                    ticket_id = ticket.save(tx=tx)

                    initial_comment = ticket_data.get("initial_comment")
                    if initial_comment and ticket_id:
                        ticket.add_comment(ticket_data.get("created_by"), initial_comment, tx=tx)

                    snap_payload = TicketController._build_snapshot_payload(
                        ticket_data, participant, ticket_id=ticket_id, attempt_id=attempt_id
                    )
                    ClassificationTraceService.save_snapshot(snap_payload, tx=tx)

                    if recording_id:
                        changed_rec = AudioArchive.finish(
                            recording_id, ticket_id=ticket_id, transcript=transcript, error_code=None, tx=tx
                        )
                        if not changed_rec:
                            raise RuntimeError('No se pudo vincular la grabación de audio al ticket.')

                    if attempt_id and has_request_context() and getattr(g, 'measurement_attempt_id', None) == attempt_id and hasattr(g, 'measurement_started_perf'):
                        changed_att, total_ms = MeasurementService.finish_in_tx(
                            tx,
                            attempt_id,
                            session['user_id'],
                            perf_counter() - g.measurement_started_perf,
                            ticket_id,
                            origin,
                            kind,
                            len((ticket_data.get('description') or '').split()),
                        )
                        if not changed_att:
                            raise RuntimeError('El intento de medición ya no se encontraba en procesamiento.')

            if has_request_context():
                g.created_ticket_id = ticket_id
                if total_ms is not None:
                    g.measurement_finalized = True
                    g.measurement_total_ms = total_ms

            if not already_persisted:
                notify(ticket_id, 'created', f'Nuevo {"pedido" if kind == "request" else "reporte"} #{ticket_id} de {area["name"]}.')

            return {
                "status": "success",
                "message": "Reporte creado correctamente",
                "id": ticket_id,
                "already_persisted": already_persisted,
                "persisted_in_db": True,
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
            snapshot, changes = ClassificationTraceService.get_ticket_trace(ticket_id)
            result = {
                "ticket": ticket,
                "comments": comments,
                "classification_snapshot": snapshot,
                "classification_changes": changes,
            }
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
            previous_request_kind = ticket.request_kind
            previous_priority = ticket.priority
            ticket.request_kind = ticket_data.get('request_kind', ticket.request_kind)
            if ticket.request_kind not in ('incident','request'):
                raise ValueError('Tipo de solicitud no válido.')
            ticket.title = ticket_data.get("title", ticket.title)
            ticket.description = ticket_data.get("description", ticket.description)
            ticket.priority = ticket_data.get("priority", ticket.priority)

            classification_changed = (
                ticket.request_kind != previous_request_kind
                or ticket.priority != previous_priority
            )
            change_reason = (
                ticket_data.get('classification_change_reason')
                or ticket_data.get('update_comment')
                or ''
            ).strip()
            if classification_changed and not change_reason:
                raise ValueError('Registra el motivo del cambio cuando modifiques el tipo o la prioridad del reporte.')

            previous_status = ticket.status
            previous_assignee = ticket.assigned_to
            ticket.status = ticket_data.get("status", ticket.status)
            now = utc_now()
            ticket.resolved_at = now if ticket.status in ('resolved', 'closed') else None
            ticket.assigned_to = ticket_data.get("assigned_to", ticket.assigned_to)
            ticket.related_asset = ticket_data.get("related_asset", ticket.related_asset)
            ticket.updated_by = ticket_data.get("updated_by")
            ticket.updated_at = now

            update_comment = ticket_data.get("update_comment")
            db = Database()
            with db.transaction() as tx:
                ticket.save(tx=tx)

                if classification_changed:
                    snap_rows = tx.query(
                        'SELECT id, is_provisional FROM classification_snapshots WHERE ticket_id=%s ORDER BY created_at ASC LIMIT 1',
                        (ticket_id,),
                    )
                    snap = snap_rows[0] if snap_rows else None
                    editor_participant = ParticipantService.ensure_for_user(ticket_data['updated_by'], tx=tx) if ticket_data.get('updated_by') else None
                    ClassificationTraceService.record_human_change(
                        {
                            'ticket_id': ticket_id,
                            'snapshot_id': snap['id'] if snap else None,
                            'changed_by': ticket_data.get('updated_by'),
                            'participant_id': editor_participant['id'] if editor_participant else None,
                            'participant_code': editor_participant['code'] if editor_participant else None,
                            'previous_request_kind': previous_request_kind,
                            'new_request_kind': ticket.request_kind,
                            'previous_priority': previous_priority,
                            'new_priority': ticket.priority,
                            'change_reason': change_reason,
                            'was_provisional': snap['is_provisional'] if snap else None,
                        },
                        tx=tx,
                    )
                    if ticket_data.get('updated_by'):
                        diffs = []
                        if previous_request_kind != ticket.request_kind:
                            diffs.append(f'tipo: {previous_request_kind} → {ticket.request_kind}')
                        if previous_priority != ticket.priority:
                            diffs.append(f'prioridad: {previous_priority} → {ticket.priority}')
                        ticket.add_comment(
                            ticket_data['updated_by'],
                            f"Clasificación ajustada por TI ({', '.join(diffs)}). Motivo: {change_reason}",
                            tx=tx,
                        )

                if previous_status != ticket.status and ticket_data.get('updated_by'):
                    from utils.helpers import translate_ticket_status
                    ticket.add_comment(ticket_data['updated_by'], f"Estado actualizado: {translate_ticket_status(previous_status)} → {translate_ticket_status(ticket.status)}", tx=tx)

                if update_comment:
                    ticket.add_comment(ticket_data.get("updated_by"), update_comment, tx=tx)

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
