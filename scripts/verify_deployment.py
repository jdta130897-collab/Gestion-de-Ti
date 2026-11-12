"""Verifica salud, almacenamiento de activos y API keys con un usuario temporal."""
import sys
import uuid
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app
from config.database import Database
from models.asset import Asset
from models.user import User
from services.area_service import AreaService
from services.auth_service import AuthService

db=Database()
client=app.test_client()
assert client.get('/healthz').status_code==200
assert client.get('/static/css/live-insights.css').status_code==200
assert app.config['SESSION_COOKIE_HTTPONLY']
assert app.config['SESSION_COOKIE_SAMESITE']=='Lax'
assert app.config['MAX_CONTENT_LENGTH']==4194304
user=User(name='QA deployment',email=uuid.uuid4().hex+'@example.invalid',password=uuid.uuid4().hex,role='super_admin',area_id=AreaService.ti_id())
user.save()
asset=None
try:
    result=Asset().create(dict(name='QA deployment asset',type='hardware',status='active',purchase_date=date.today(),assigned_to=user.id))
    assert result['status']=='success',result
    asset=result['id']
    assert Asset().get_by_id(asset)['data']['name']=='QA deployment asset'
    assert Asset().update(asset,dict(name='Updated',type='hardware',status='active',purchase_date=date.today(),assigned_to=user.id))['status']=='success'
    assert Asset().delete(asset)['status']=='success'
    asset=None
    assert AuthService().generate_api_key(user.id)
    print('OK: salud, cookies, límite de carga, recursos estáticos, CRUD de activos y API keys.')
finally:
    if asset:db.execute_update('DELETE FROM assets WHERE id=%s',(asset,))
    db.execute_update('DELETE FROM users WHERE id=%s',(user.id,))
