"""QA de navegador aislado: no usa perfiles del usuario ni envía audio al proveedor."""
import asyncio
import base64
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import urllib.request
import uuid
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import websockets
from app import app
from config.database import Database
from models.user import User
from services.area_service import AreaService
from controllers.ticket_controller import TicketController

root=Path(__file__).resolve().parents[1]
base_url=os.getenv('BROWSER_TEST_BASE_URL','http://127.0.0.1:5000').rstrip('/')
out=root/'.runtime/browser-insights'
out.mkdir(parents=True,exist_ok=True)
chrome=Path(os.environ['ProgramFiles'])/'Google/Chrome/Application/chrome.exe'
results=[]
db=Database()
password=uuid.uuid4().hex
user=User(name='Prueba visual temporal',email=uuid.uuid4().hex+'@example.invalid',password=password,role='user',area_id=AreaService.ti_id())
uid=user.save()
client=app.test_client();client.post('/login',data={'email':user.email,'password':password})
cookie=client.get_cookie('session').value
process=None


def check(value,label):
    assert value,label
    results.append(label);print('OK',label,flush=True)


async def run():
    global process
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    process=subprocess.Popen([str(chrome),'--headless=new','--disable-gpu','--remote-debugging-port=9237',f'--user-data-dir={out / ("profile-"+uuid.uuid4().hex[:6])}', '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','about:blank'],stdout=subprocess.DEVNULL,stderr=open(out/'chromium-error.log','wb'),startupinfo=startup)
    for _ in range(50):
        if process.poll() is not None:
            raise RuntimeError('Chromium terminó con código '+str(process.returncode)+': '+(out/'chromium-error.log').read_text(errors='replace'))
        try:
            targets=json.load(urllib.request.urlopen('http://127.0.0.1:9237/json',timeout=1));break
        except Exception:await asyncio.sleep(.2)
    else:raise RuntimeError('No inició el navegador de pruebas.')
    target=next(t for t in targets if t['type']=='page')
    async with websockets.connect(target['webSocketDebuggerUrl'],max_size=20_000_000) as ws:
        counter=0
        async def call(method,params=None):
            nonlocal counter
            counter+=1;ident=counter
            await ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
            while True:
                message=json.loads(await ws.recv())
                if message.get('method')=='Fetch.requestPaused':
                    # Solo la interfaz del grabador usa una respuesta simulada; no hay llamada a AssemblyAI.
                    paused=message['params'];counter+=1
                    body=json.dumps({'mensaje':'Prueba visual simulada','ticket_id':ticket_id,'total_ms':3450})
                    await ws.send(json.dumps({'id':counter,'method':'Fetch.fulfillRequest','params':{'requestId':paused['requestId'],'responseCode':201,'responseHeaders':[{'name':'Content-Type','value':'application/json'}],'body':base64.b64encode(body.encode()).decode()}}))
                if message.get('id')==ident:
                    if 'error' in message:raise RuntimeError(str(message['error']))
                    return message.get('result',{})
        async def evaluate(code):
            result=await call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
            if result.get('exceptionDetails'):raise RuntimeError(str(result['exceptionDetails']))
            return result.get('result',{}).get('value')
        async def wait(code,timeout=20):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                if await evaluate(code):return
                await asyncio.sleep(.2)
            raise AssertionError('Tiempo agotado: '+code)
        async def navigate(path):
            await call('Page.navigate',{'url':base_url+path})
            await wait("document.readyState==='complete'")
        async def screenshot(name):
            result=await call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
            (out/name).write_bytes(base64.b64decode(result['data']))
        await call('Network.enable')
        await call('Network.setCookie',{'name':'session','value':cookie,'domain':urlsplit(base_url).hostname,'path':'/','secure':base_url.startswith('https:')})
        for width in (320,360,390,430):
            await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':844,'deviceScaleFactor':1,'mobile':True})
            for path in ('/dashboard','/tickets','/tickets/create','/chatbot'):
                await navigate(path)
                check(await evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Pantalla {path} sin desbordamiento a {width}px')
            await evaluate("document.getElementById('menu-toggle').click()")
            check(await evaluate("document.body.classList.contains('menu-open')"),f'Menú táctil abre a {width}px')
            await evaluate("document.getElementById('menu-close').click()")
            check(await evaluate("!document.body.classList.contains('menu-open')"),f'Menú táctil cierra a {width}px')
        await call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        await navigate('/tickets/create')
        await wait("typeof CreationTimer==='function'")
        await evaluate("document.querySelector('[name=subject]').value='Prueba visual del temporizador';document.querySelector('[name=subject]').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('[name=description]').value='Descripción de prueba para verificar guardado y cronómetro.'")
        await wait("document.getElementById('attempt_id').value.length>0")
        first=await evaluate("document.querySelector('[data-timer-value]').textContent")
        await asyncio.sleep(.4)
        check(first!=await evaluate("document.querySelector('[data-timer-value]').textContent"),'Cronómetro manual avanza en navegador')
        await screenshot('manual-timer.png')
        await evaluate("document.querySelector('form[data-creation-channel] button[type=submit]').click()")
        await wait("location.pathname==='/tickets'")
        rows=db.execute_query('SELECT id FROM tickets WHERE created_by=%s',(uid,))
        check(len(rows)==1,'Formulario medido se guarda sin duplicados')
        ticket_id=rows[0]['id']
        check(db.execute_query("SELECT id FROM creation_attempts WHERE ticket_id=%s AND outcome='success'",(ticket_id,)),'Medición del navegador persiste en la base de datos')
        await navigate('/dashboard')
        await wait("document.getElementById('metric-count')?.textContent==='1'")
        check(await evaluate("typeof Chart==='function' && [...document.querySelectorAll('canvas')].every(c=>Chart.getChart(c))"),'Siete gráficos activos sin errores de inicialización')
        aid=client.post('/api/measurements/start',json={'channel':'manual','request_kind':'request'}).json['attempt_id']
        client.post('/tickets/create',data={'attempt_id':aid,'subject':'Segunda solicitud de prueba visual','description':'Solicitud temporal para comprobar actualización automática.','priority':'medium','request_kind':'request'})
        await wait("document.getElementById('metric-count').textContent==='2'",timeout=12)
        check(True,'Dashboard actualiza las mediciones sin recargar la página')
        TicketController.add_comment(ticket_id,{'user_id':uid,'comment':'Aviso temporal para comprobar notificaciones.'})
        await wait("Number(document.getElementById('notification-count').textContent)>=1",timeout=12)
        check(True,'Campana recibe notificaciones sin recargar la página')
        await evaluate("document.getElementById('analytics-workspace').scrollIntoView()")
        await screenshot('dashboard-desktop.png')
        await call('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(out)})
        image=out/'comparativa-time-4K.png'
        if image.exists():image.unlink()
        await evaluate("document.querySelector('[data-download-png=time]').click()")
        for _ in range(50):
            if image.exists():break
            await asyncio.sleep(.2)
        check(image.exists(),'Descarga PNG desde el botón del dashboard')
        check(struct.unpack('>II',image.read_bytes()[16:24])==(3840,2160),'Imagen exportada mide 3840 × 2160 píxeles')
        await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        await asyncio.sleep(.3)
        check(await evaluate('document.documentElement.scrollWidth<=window.innerWidth'),'Dashboard móvil sin desbordamiento horizontal')
        check(await evaluate("document.getElementById('notification-toggle').getBoundingClientRect().height>0"),'Campana accesible en la cabecera móvil')
        await evaluate("document.getElementById('notification-toggle').click()")
        await wait("document.querySelector('.notification-menu').classList.contains('show')")
        check(await evaluate("document.querySelector('.notification-menu').getBoundingClientRect().right<=innerWidth"),'Notificaciones móviles dentro del ancho de pantalla')
        await screenshot('dashboard-mobile.png')
        await call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        await navigate('/chatbot')
        await wait("typeof CreationTimer==='function'")
        await evaluate("document.getElementById('start-btn').click()")
        check(await evaluate("document.getElementById('status').textContent.includes('Autoriza') && !document.getElementById('start-btn').disabled"),'Grabación exige autorizar la conservación privada antes de activar el micrófono')
        await call('Fetch.enable',{'patterns':[{'urlPattern':'*/api/tickets/voz','requestStage':'Request'}]})
        await evaluate("document.getElementById('retain-audio').checked=true;document.getElementById('start-btn').click()")
        await wait("document.getElementById('status').textContent.includes('Grabando')")
        check(await evaluate("!document.getElementById('stop-btn').disabled && document.getElementById('start-btn').disabled"),'Grabador inicia con temporizador y evita doble inicio')
        await screenshot('voice-recording.png')
        check(await evaluate("document.querySelector('.voice-visualizer').dataset.voiceState==='recording' && getComputedStyle(document.querySelector('.voice-orbit')).animationName==='voice-spin' && document.querySelectorAll('.voice-waveform span').length===11"),'Ondas y anillo animados durante la grabación')
        await evaluate("document.getElementById('stop-btn').click()")
        await wait("document.getElementById('status').textContent.includes('Solicitud creada')")
        check(await evaluate("document.querySelector('.voice-visualizer').dataset.voiceState==='success' && getComputedStyle(document.querySelector('.voice-orbit')).animationName==='none'"),'Animación detenida al completar el reporte')
        check(await evaluate("document.querySelector('[data-timer-value]').textContent==='00:03.5'"),'Grabador muestra el tiempo confirmado y detiene el cronómetro')
        await call('Fetch.disable')
        await navigate('/login')
        await evaluate("document.querySelector('[name=email]').value='incorrecto@example.invalid';document.querySelector('[name=password]').value='incorrecta';document.querySelector('form').requestSubmit()")
        await wait("document.querySelector('.alert-dismissible')!==null")
        await asyncio.sleep(5.4)
        check(await evaluate("document.querySelector('.alert-dismissible')===null"),'Aviso de contraseña incorrecta desaparece a los cinco segundos')
        # Validar la representación gráfica vectorial en el motor del navegador.
        await navigate('/reports/analytics')
        await wait("document.querySelectorAll('svg').length===7")
        await screenshot('report.png')
        check(await evaluate("document.querySelector('h1').textContent.includes('registro manual')"),'Informe imprimible carga con sus gráficos')
finally_message=''
try:
    asyncio.run(run())
finally:
    if process:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill()
    for row in db.execute_query('SELECT id FROM tickets WHERE created_by=%s',(uid,)):
        TicketController.delete_ticket(row['id'])
    db.execute_update('DELETE FROM users WHERE id=%s',(uid,))
    (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('Comprobaciones de navegador:',len(results))
