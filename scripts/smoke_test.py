import sys,uuid,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app
from config.database import Database
from controllers.ticket_controller import TicketController
from controllers.user_controller import UserController
from controllers.asset_controller import AssetController
from controllers.monitoring_controller import MonitoringController
app.testing=True
c=app.test_client();db=Database();tag='Verificacion '+uuid.uuid4().hex[:8];report=[]
def ok(value,label):
 assert value,label
 report.append(label);print('OK',label)
def success(r,label):
 ok(r.get('status')=='success',label+': '+str(r.get('message','')));return r.get('id')
u=a=t=None
try:
 ok(c.get('/dashboard').status_code==302,'Acceso requiere sesion')
 ok(c.post('/login',data={'email':'admin@example.com','password':'incorrecta'}).status_code==200,'Rechazo de clave incorrecta')
 ok(c.post('/login',data={'email':'admin@example.com','password':'admin123'}).location=='/dashboard','Login contra base de datos')
 for p in ['/dashboard','/assets','/assets/create','/tickets','/tickets/create','/monitoring','/monitoring/add','/users','/users/create','/profile','/settings','/chatbot']:
  ok(c.get(p).status_code==200,'GET '+p)
 u=success(UserController.create_user({'name':tag,'email':uuid.uuid4().hex+'@example.com','password':'Verificacion123','role':'technician'}),'Crear usuario')
 ok(db.execute_query('SELECT id FROM users WHERE id=%s',(u,))[0]['id']==u,'ID usuario y persistencia')
 success(UserController.update_user(u,{'name':tag+' editado'}),'Editar usuario')
 a=success(AssetController.create_asset({'name':tag,'type':'hardware','status':'active','purchase_date':'2026-11-06','assigned_to':u}),'Crear activo')
 ok(db.execute_query('SELECT name FROM assets WHERE id=%s',(a,))[0]['name']==tag,'Activo persistido en MySQL')
 success(AssetController.update_asset(a,{'name':tag+' editado','type':'hardware','status':'maintenance','purchase_date':'2026-11-06','assigned_to':u}),'Editar activo')
 t=success(TicketController.create_ticket({'title':tag,'description':'Prueba real de persistencia y comentarios','priority':'high','status':'open','created_by':1,'assigned_to':u,'related_asset':a,'initial_comment':'Comentario inicial de prueba'}),'Crear ticket con comentario')
 ok(len(db.execute_query('SELECT id FROM ticket_comments WHERE ticket_id=%s',(t,)))==1,'Comentario asociado al ID correcto')
 success(TicketController.update_ticket(t,{'title':tag+' editado','description':'Descripcion actualizada de prueba','priority':'medium','status':'resolved','updated_by':1}),'Editar ticket')
 success(TicketController.add_comment(t,{'user_id':1,'comment':'Seguimiento de prueba'}),'Comentar ticket')
 success(MonitoringController.add_metric({'asset_id':a,'metric_name':'cpu_usage','metric_value':42}),'Guardar monitoreo')
 for p in [f'/assets/{a}',f'/assets/{a}/edit',f'/tickets/{t}',f'/tickets/{t}/edit',f'/users/{u}/edit','/dashboard','/monitoring','/profile']:
  ok(c.get(p).status_code==200,'GET con datos '+p)
 success(UserController.update_user(u,{'is_active':False}),'Desactivar usuario')
 ok(not db.execute_query('SELECT is_active FROM users WHERE id=%s',(u,))[0]['is_active'],'Desactivacion persistida')
finally:
 if t:TicketController.delete_ticket(t)
 if a:AssetController.delete_asset(a)
 if u:UserController.delete_user(u)
 Path('.runtime/smoke-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Comprobaciones completadas:',len(report))
