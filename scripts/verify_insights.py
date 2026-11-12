"""Verifica métricas y notificaciones con fixtures aislados y transcripción simulada."""
import io
import json
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from config.database import Database
from models.user import User
from controllers.ticket_controller import TicketController
from services.area_service import AreaService

app.testing=True
db=Database(); results=[]; users=[]; tickets=[]; areas=[]
tag=uuid.uuid4().hex[:8]; password=uuid.uuid4().hex
tables=('users','tickets','ticket_comments','areas','creation_attempts','notifications')
baseline={t:db.execute_query(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] for t in tables}


def check(value,label):
    assert value,label
    results.append(label);print('OK',label)


def person(role,area):
    u=User(name='Prueba '+tag,email=uuid.uuid4().hex+'@example.invalid',password=password,role=role,area_id=area)
    users.append(u.save());c=app.test_client();c.post('/login',data={'email':u.email,'password':password})
    return u.id,c


def attempt(client,channel,seconds):
    r=client.post('/api/measurements/start',json={'channel':channel,'request_kind':'request'})
    check(r.status_code==201,'Iniciar temporizador '+channel)
    aid=r.json['attempt_id']
    db.execute_update('UPDATE creation_attempts SET started_at=UTC_TIMESTAMP(6)-INTERVAL %s SECOND WHERE id=%s',(seconds,aid))
    return aid


try:
    a=AreaService.save('Área métricas '+tag,'M'+tag);areas.append(a)
    b=AreaService.save('Área privada '+tag,'N'+tag);areas.append(b)
    super_id,super_client=person('super_admin',AreaService.ti_id())
    admin_id,admin=person('admin',AreaService.ti_id())
    uid,client=person('user',a)
    manager_id,manager=person('manager',a)
    foreign_id,foreign=person('user',b)
    empty=client.get('/api/analytics').json
    check(empty['channels']['voice']['mean_s'] is None and empty['reduction_pct'] is None,'Sin datos no se inventan tiempos ni ventaja')
    check(app.test_client().get('/api/analytics').status_code==302,'Métricas requieren autenticación')
    check(client.post('/api/measurements/start',json={'channel':'invalido'}).status_code==400,'Canal inválido rechazado')
    aid=attempt(client,'manual',10)
    bad=foreign.post('/tickets/create',data={'attempt_id':aid,'subject':'Manipulado '+tag,'description':'Descripción de prueba válida','priority':'medium'})
    check(db.execute_query('SELECT outcome FROM creation_attempts WHERE id=%s',(aid,))[0]['outcome']=='started','Otro usuario no puede utilizar el temporizador')
    payload={'attempt_id':aid,'subject':'Medición manual '+tag,'description':'Descripción real de fixture para verificar medición.','priority':'medium','request_kind':'request'}
    response=client.post('/tickets/create',data=payload)
    row=db.execute_query('SELECT * FROM creation_attempts WHERE id=%s',(aid,))[0]
    if row['ticket_id']:tickets.append(row['ticket_id'])
    check(response.status_code==302 and row['outcome']=='success' and row['total_ms']>=10000,'Medición manual persistente y exitosa')
    check(row['processing_ms']>=0 and row['preparation_ms']>=10000,'Preparación y procesamiento separados')
    client.post('/tickets/create',data=payload)
    check(len(db.execute_query('SELECT id FROM tickets WHERE title=%s',(payload['subject'],)))==1,'Reenvío del mismo intento no duplica solicitudes')
    aid_voice=attempt(client,'voice',2)
    with patch('controllers.ticket_controller.voice_service.transcribe_audio',return_value='Solicito acceso importante a un programa para mi trabajo del área.'):
        response=client.post('/api/tickets/voz',data={'attempt_id':aid_voice,'request_kind':'request','audio':(io.BytesIO(b'fixture'),'audio.webm')},content_type='multipart/form-data')
    if response.json.get('ticket_id'):tickets.append(response.json['ticket_id'])
    check(response.status_code==201 and response.json.get('total_ms')>=2000,'Voz registra el tiempo completo y confirma el guardado')
    summary=client.get('/api/analytics').json
    check(summary['channels']['manual']['success']==1 and summary['channels']['voice']['success']==1,'Conteo de éxitos por canal')
    check(summary['reduction_pct']>0,'Reducción calculada con valores medidos')
    manual=db.execute_query('SELECT total_ms FROM creation_attempts WHERE id=%s',(aid,))[0]['total_ms']/1000
    check(abs(summary['channels']['manual']['mean_s']-manual)<.001,'Promedio corresponde a la base de datos')
    check(summary['channels']['manual']['median_s']==summary['channels']['manual']['p90_s'],'Mediana y P90 correctos con una observación')
    db.execute_update('UPDATE creation_attempts SET total_ms=60000 WHERE id=%s',(aid_voice,))
    check(client.get('/api/analytics').json['reduction_pct']<0,'El sistema también informa cuando el registro manual es más rápido')
    db.execute_update('UPDATE creation_attempts SET total_ms=3000 WHERE id=%s',(aid_voice,))
    failed=attempt(client,'voice',1)
    with patch('controllers.ticket_controller.voice_service.transcribe_audio',side_effect=ValueError('Fallo simulado del proveedor')):
        response=client.post('/api/tickets/voz',data={'attempt_id':failed,'audio':(io.BytesIO(b'fixture'),'fallo.webm')},content_type='multipart/form-data')
    check(response.status_code==400,'Fallo de transcripción devuelve error')
    summary=client.get('/api/analytics').json
    check(summary['channels']['voice']['failed']==1 and summary['channels']['voice']['success_rate']==50,'Fallos incluidos en tasa de éxito')
    abandoned=attempt(client,'manual',1)
    client.post('/api/measurements/'+abandoned+'/abandon')
    check(client.get('/api/analytics').json['channels']['manual']['abandoned']==1,'Abandono identificado sin contarlo como éxito')
    stale=attempt(client,'manual',1)
    db.execute_update('UPDATE creation_attempts SET started_at=UTC_TIMESTAMP(6)-INTERVAL 3 HOUR WHERE id=%s',(stale,))
    check(client.get('/api/analytics').json['channels']['manual']['abandoned']==2,'Intentos vencidos se clasifican como abandonados')
    private=foreign.get('/api/analytics').json
    check(private['measured_success']==0 and private['channels']['voice']['attempts']==0,'Estadísticas aisladas entre áreas y usuarios')
    check(manager.get('/api/analytics').json['measured_success']==2,'Responsable de área ve estadísticas de su área')
    check(super_client.get('/api/analytics').json['measured_success']>=2,'Superadministrador ve estadísticas generales')
    check(client.get('/api/analytics?kind=incident').json['measured_success']==0,'Filtro por tipo de solicitud')
    check(client.get('/api/analytics?date_from=2000-01-01&date_to=2000-01-02').json['measured_success']==0,'Filtro de período')
    check(client.get('/api/analytics?date_from=fecha-incorrecta').status_code==400,'Fechas inválidas no generan errores internos')
    check(client.get('/api/analytics?date_from=2030-01-01&date_to=2000-01-01').status_code==400,'Rango de fechas invertido rechazado')
    inbox=admin.get('/api/notifications').json
    check(inbox['unread']>=2 and any(r['ticket_id']==tickets[0] for r in inbox['items']),'TI recibe avisos de nuevas solicitudes')
    notice=next(r for r in inbox['items'] if r['ticket_id']==tickets[0])
    foreign.post(f'/api/notifications/{notice["id"]}/read')
    check(db.execute_query('SELECT read_at FROM notifications WHERE id=%s',(notice['id'],))[0]['read_at'] is None,'No se pueden marcar avisos de otro usuario')
    admin.post(f'/api/notifications/{notice["id"]}/read')
    check(db.execute_query('SELECT read_at FROM notifications WHERE id=%s',(notice['id'],))[0]['read_at'] is not None,'Marcar notificación propia como leída')
    admin.post(f'/tickets/{tickets[0]}/edit',data={'subject':payload['subject'],'description':payload['description'],'priority':'high','status':'in_progress','assigned_to':admin_id,'update_comment':'Atención en curso.'})
    own=client.get('/api/notifications').json
    check(any('responsable' in r['message'] for r in own['items']),'Aviso al solicitante cuando se asigna responsable')
    check(any('En progreso' in r['message'] for r in own['items']),'Aviso por cambio de estado')
    check(any('respuesta' in r['message'] for r in own['items']),'Aviso de respuesta del equipo TI')
    check(foreign.get('/api/notifications').json['unread']==0,'Notificaciones privadas no se filtran entre áreas')
    csv=client.get('/reports/analytics.csv')
    check(csv.status_code==200 and b'attachment' in csv.headers['Content-Disposition'].encode(),'Descarga CSV con disposición de archivo')
    check(tag in csv.get_data(as_text=True),'CSV incluye las mediciones del alcance autorizado')
    check(tag not in foreign.get('/reports/analytics.csv').get_data(as_text=True),'CSV respeta los permisos')
    for chart in ('time','volume','success','phases','trend','priority','status'):
        svg=client.get('/reports/chart.svg?chart='+chart)
        check(svg.status_code==200 and ET.fromstring(svg.data).tag.endswith('svg'),'SVG vectorial válido '+chart)
        Path('.runtime/insights-'+chart+'.svg').write_bytes(svg.data)
    report=client.get('/reports/analytics')
    check(report.status_code==200 and report.get_data(as_text=True).count('<svg ')==7,'Informe imprimible con siete gráficos vectoriales')
    check('Comparación observacional' in report.get_data(as_text=True),'Informe explica el alcance de la comparación')
    check('attachment' in client.get('/reports/analytics?download=1').headers['Content-Disposition'],'Informe descargable en HTML')
    Path('.runtime/insights-report.html').write_bytes(report.data)
    html=client.get('/dashboard').get_data(as_text=True)
    check('analytics-workspace' in html and 'notifications.js' in html and '5000' in html,'Dashboard, notificaciones y avisos de cinco segundos integrados')
    check('data-creation-channel="manual"' in client.get('/tickets/create').get_data(as_text=True),'Temporizador integrado al formulario manual')
    check('voice_recorder.js' in client.get('/chatbot').get_data(as_text=True),'Grabador con temporizador integrado')
finally:
    for tid in tickets:TicketController.delete_ticket(tid)
    for uid in users:db.execute_update('DELETE FROM users WHERE id=%s',(uid,))
    for area in areas:db.execute_update('DELETE FROM areas WHERE id=%s',(area,))
    after={t:db.execute_query(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] for t in tables}
    check(after==baseline,'Fixtures eliminados y datos anteriores conservados')
    Path('.runtime/insights-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('Comprobaciones completadas:',len(results))
