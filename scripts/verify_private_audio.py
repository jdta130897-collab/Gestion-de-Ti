"""Fixtures aislados: audio WAV real de silencio; transcripción simulada, sin proveedor."""
import io
import hashlib
import sys
import uuid
import wave
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app
from models.user import User
from config.database import Database
from services.area_service import AreaService
from utils.release import SOFTWARE_VERSION

app.testing=True
db=Database();users=[];results=[]
tables=('users','tickets','creation_attempts','research_participants','voice_recordings')
before={t:db.execute_query(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] for t in tables}
original_versions={r['id']:r['software_version'] for r in db.execute_query('SELECT id,software_version FROM creation_attempts')}
buffer=io.BytesIO()
with wave.open(buffer,'wb') as wav:
    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0'*3200)
audio=buffer.getvalue()

def check(value,label):
    assert value,label
    results.append(label);print('OK',label,flush=True)

def person(role):
    password=uuid.uuid4().hex
    user=User(name='QA audio',email=uuid.uuid4().hex+'@example.invalid',password=password,role=role,area_id=AreaService.ti_id());user.save();users.append(user.id)
    client=app.test_client();client.post('/login',data={'email':user.email,'password':password})
    return user,client

def upload(client,text='La impresora presenta un problema importante y necesita asistencia.',consent=True,failure=False):
    aid=client.post('/api/measurements/start',json={'channel':'voice','request_kind':'incident'}).json['attempt_id']
    data={'attempt_id':aid,'audio':(io.BytesIO(audio),'prueba.wav')}
    if consent:data['retain_audio']='1'
    kwargs={'side_effect':RuntimeError('Fallo simulado')} if failure else {'return_value':text}
    with patch('controllers.ticket_controller.voice_service.transcribe_audio',**kwargs), patch('controllers.ticket_controller.voice_service.classify_ticket', return_value={'priority':'medium','request_kind':'incident','category':'general','reason':'Clasificación simulada'}):
        response=client.post('/api/tickets/voz',data=data,content_type='multipart/form-data')
    return aid,response

try:
    owner,client=person('user');other,foreign=person('user');admin,super_client=person('super_admin');tech,technical=person('technician')
    aid,response=upload(client,consent=False)
    check(response.status_code==400,'Consentimiento obligatorio en el servidor')
    check(not db.execute_query('SELECT id FROM voice_recordings WHERE attempt_id=%s',(aid,)),'Sin autorización no se archiva audio')
    aid,response=upload(client)
    check(response.status_code==201,'Audio autorizado crea el reporte')
    recording=db.execute_query('SELECT * FROM voice_recordings WHERE attempt_id=%s',(aid,))[0]
    rid=recording['id'];ticket=response.json['ticket_id']
    check(bytes(recording['audio_data'])==audio,'Bytes originales persistidos en la base de datos')
    check(recording['sha256']==hashlib.sha256(audio).hexdigest(),'Integridad SHA-256 verificable')
    check(recording['ticket_id']==ticket and recording['user_id']==owner.id,'Asociación al intento, ticket y propietario')
    check(recording['software_version']==SOFTWARE_VERSION,'Versión del audio registrada')
    check(db.execute_query('SELECT software_version FROM creation_attempts WHERE id=%s',(aid,))[0]['software_version']==SOFTWARE_VERSION,'Versión de la medición registrada')
    participant=db.execute_query('SELECT * FROM research_participants WHERE user_id=%s',(owner.id,))[0]
    check(participant['code'].startswith('P-') and owner.email not in participant['code'],'Participante codificado sin incluir nombre o correo')
    check(recording['consent_at'] is not None and recording['transcript'],'Consentimiento y transcripción conservados')
    path='/recordings/'+rid+'/audio'
    download=client.get(path)
    check(download.status_code==200 and download.data==audio,'Descarga autenticada reproduce los bytes originales')
    check('no-store' in download.headers['Cache-Control'],'Audio excluido de caché pública')
    check(app.test_client().get(path).status_code==302,'Descarga sin sesión bloqueada')
    check(foreign.get(path).status_code==404,'Otro participante no puede descargar el audio')
    check(technical.get(path).status_code==404,'Rol técnico no concede acceso al audio privado')
    check(super_client.get(path).status_code==200,'Superadministrador autorizado')
    check(not foreign.get('/api/recordings').json['items'],'Listado no filtra grabaciones de otras cuentas')
    check(client.get('/recordings').status_code==200,'Pantalla de audios privados disponible')
    with patch('controllers.ticket_controller.voice_service.transcribe_audio') as transcribe:
        replay=client.post('/api/tickets/voz',data={'attempt_id':aid,'retain_audio':'1','audio':(io.BytesIO(audio),'repetido.wav')})
        check(replay.status_code==200 and not transcribe.called,'Reintento confirmado no transcribe ni duplica')
    check(len(db.execute_query('SELECT id FROM voice_recordings WHERE attempt_id=%s',(aid,)))==1,'Un audio por intento')
    failed,reply=upload(client,failure=True)
    failure=db.execute_query('SELECT * FROM voice_recordings WHERE attempt_id=%s',(failed,))[0]
    check(reply.status_code==400 and failure['outcome']=='failed' and bytes(failure['audio_data'])==audio,'Fallo del proveedor conserva audio y resultado fallido')
    check(failure['ticket_id'] is None,'Un fallo no inventa un ticket')
    silent,reply=upload(client,text='   ')
    check(reply.status_code==400 and db.execute_query('SELECT outcome FROM voice_recordings WHERE attempt_id=%s',(silent,))[0]['outcome']=='failed','Transcripción vacía no genera ticket y conserva el audio')
    check(len(db.execute_query('SELECT id FROM research_participants WHERE user_id=%s',(owner.id,)))==1,'Código de participante estable entre intentos')
    check(foreign.post('/recordings/'+rid+'/delete').status_code==404,'Eliminación ajena bloqueada')
    check(client.post('/recordings/'+rid+'/delete').status_code==302,'Propietario elimina su grabación')
    check(client.get(path).status_code==404,'Audio eliminado deja de descargarse')
    check(db.execute_query('SELECT id FROM tickets WHERE id=%s',(ticket,)),'Eliminar audio conserva ticket')
    check(db.execute_query('SELECT id FROM creation_attempts WHERE id=%s',(aid,)),'Eliminar audio conserva medición')
    current_versions={r['id']:r['software_version'] for r in db.execute_query('SELECT id,software_version FROM creation_attempts')}
    check(all(current_versions.get(k)==v for k,v in original_versions.items()),'Las versiones de los intentos históricos permanecen intactas')
finally:
    for uid in users:
        db.execute_update('DELETE FROM tickets WHERE created_by=%s',(uid,))
        db.execute_update('DELETE FROM users WHERE id=%s',(uid,))
    after={t:db.execute_query(f'SELECT COUNT(*) AS n FROM {t}')[0]['n'] for t in tables}
    check(after==before,'Fixtures eliminados y datos anteriores conservados')
print('Comprobaciones:',len(results))
