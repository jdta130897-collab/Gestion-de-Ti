"""Pruebas aisladas de permisos, inmutabilidad y matriz, sin llamadas externas."""
import sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app
from config.database import Database
from models.user import User
from controllers.ticket_controller import TicketController
from services.voice_service import VoiceService
from services.area_service import AreaService
app.testing=True
db=Database(); ids=[]; tids=[]; checks=[]
def check(v,label):
 assert v,label
 checks.append(label);print('OK',label,flush=True)
def user(role,area):
 u=User(name='QA flujo',email=uuid.uuid4().hex+'@example.invalid',password=uuid.uuid4().hex,role=role,area_id=area);u.save();ids.append(u.id);return u
area=db.execute_update('INSERT INTO areas(code,name) VALUES(%s,%s)',('Q'+uuid.uuid4().hex[:10],uuid.uuid4().hex),return_id=True)
try:
 manager=user('manager',area);worker=user('user',area);other=user('user',AreaService.ti_id());superuser=user('super_admin',area)
 tid=db.execute_update("INSERT INTO tickets(title,description,status,priority,created_by,origin_area_id,destination_area_id,request_kind,channel,created_at,updated_at) VALUES('Prueba flujo','Descripción suficientemente larga','open','medium',%s,%s,%s,'incident','manual',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",(worker.id,area,area),return_id=True);tids.append(tid)
 def update(actor,data):
  with app.test_request_context('/'):
   from flask import session
   session.update(user_id=actor.id,user_role=actor.role,area_id=actor.area_id)
   return TicketController.update_ticket(tid,data)
 check(update(worker,{'assigned_to':worker.id})['status']=='error','Trabajador no puede autoasignarse')
 check(update(superuser,{'assigned_to':worker.id})['status']=='error','Superadministrador no suplanta al encargado')
 check(update(manager,{'assigned_to':other.id})['status']=='error','No se asignan trabajadores de otra área')
 check(update(manager,{'request_kind':'request','priority':'high'})['status']=='success','Encargado corrige clasificación antes de asignar')
 check(update(manager,{'assigned_to':worker.id})['status']=='success','Encargado asigna a trabajador de su área')
 check(update(manager,{'priority':'low'})['status']=='error','Prioridad bloqueada después de asignar')
 check(update(manager,{'request_kind':'incident'})['status']=='error','Tipo bloqueado después de asignar')
 check(update(worker,{'status':'in_progress'})['status']=='success','Trabajador asignado atiende el ticket')
 check(update(manager,{'assigned_to':None})['status']=='success','Encargado puede retirar la asignación')
 check(update(manager,{'priority':'low'})['status']=='error','Retirar responsable no desbloquea clasificación')
 check(update(manager,{'assigned_to':worker.id})['status']=='success','Encargado reasigna dentro del área')
 check(update(worker,{'status':'resolved'})['status']=='error','Resolver exige respuesta')
 check(update(worker,{'status':'resolved','update_comment':'Solución registrada'})['status']=='success','Trabajador resuelve con respuesta')
 check(update(manager,{'title':'Alteración posterior'})['status']=='error','Resuelto no admite edición')
 try:
  db.execute_update("UPDATE tickets SET description='Cambio SQL' WHERE id=%s",(tid,));blocked=False
 except Exception:blocked=True
 check(blocked,'Base de datos también impide editar tickets resueltos')
 try:AreaService.validate_membership('manager',area);blocked=False
 except ValueError:blocked=True
 check(blocked,'Un solo encargado activo por área')
 for impact,urgency,priority in [('individual','routine','low'),('individual','degraded','medium'),('individual','blocked','high'),('organization','blocked','critical'),('area','blocked','high')]:
  r=VoiceService.validate_classification(dict(request_kind='incident',impact=impact,urgency=urgency,category='red',reason='Evidencia del reporte',needs_clarification=False));check(r['priority']==priority,impact+'/'+urgency+' -> '+priority)
 r=VoiceService.validate_classification(dict(request_kind='request',impact='unknown',urgency='unknown',category='general',reason='Pedido sin alcance indicado',needs_clarification=True))
 check(r['priority']=='medium' and not r['needs_clarification'],'Información incompleta se clasifica sin exigir aclaraciones')
finally:
 for tid in tids:db.execute_update('DELETE FROM tickets WHERE id=%s',(tid,))
 for uid in ids:db.execute_update('DELETE FROM users WHERE id=%s',(uid,))
 db.execute_update('DELETE FROM areas WHERE id=%s',(area,))
print('Comprobaciones:',len(checks))
