import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app
from flask import session,render_template
from utils.permissions import can_edit_ticket
from controllers.ticket_controller import TicketController
from unittest.mock import patch
app.testing=True
base={'id':999,'created_by':10,'origin_area_id':2,'destination_area_id':1,'assigned_to':11,'status':'open','title':'Prueba','description':'Prueba','priority':'medium','request_kind':'incident','created_at':None,'updated_at':None}
checks=0
for code,area,role,uid,expected in [('RRHH',2,'user',10,False),('RRHH',2,'manager',10,False),('TI',1,'manager',12,True),('TI',1,'user',11,True),('TI',1,'user',13,False),('TI',1,'super_admin',12,False)]:
 with app.test_request_context('/'):
  session.update(user_id=uid,user_role=role,area_id=area,area_code=code)
  assert can_edit_ticket(base)==expected
  html=render_template('tickets/view.html',ticket=base,comments=[],ticket_id=999)
  assert ('Agregar seguimiento' in html)==expected
  assert ('> Editar</a>' in html)==expected
  checks+=3
with app.test_request_context('/'):
 session.update(user_id=10,user_role='manager',area_id=2,area_code='RRHH')
 actor={'id':10,'is_active':True,'area_active':True,'area_code':'RRHH','area_id':2,'role':'manager'}
 with patch('services.area_service.AreaService.user_scope',return_value=actor),patch('models.ticket.Ticket.get_ticket_with_details',return_value=base):
  assert TicketController.update_ticket(999,{'title':'Intento'})['status']=='error';checks+=1
 ticket=type('TicketFixture',(),dict(status='open',destination_area_id=1,assigned_to=11))()
 with patch('models.ticket.Ticket.get_by_id',return_value=ticket),patch('services.area_service.AreaService.user_scope',return_value=actor):
  assert TicketController.add_comment(999,{'user_id':10,'comment':'Intento'})['status']=='error';checks+=1
print('Comprobaciones satisfactorias:',checks)
