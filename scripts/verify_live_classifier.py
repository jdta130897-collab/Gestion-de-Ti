"""Prueba opcional con API real: consume solicitudes de AssemblyAI; solo textos sintéticos."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.voice_service import VoiceService
cases=[('Soy la única persona afectada. Mi computadora no enciende y no tengo otra para continuar trabajando.','incident','high'),('Necesitamos instalar un programa nuevo el próximo mes para tres personas del área. Podemos trabajar normalmente.','request','medium'),('El sistema existente ha dejado de funcionar en toda la institución, todas las áreas están paralizadas y no hay alternativa.','incident','critical'),('Urgente, solicito un mouse adicional para mí para el próximo mes. Mi mouse actual funciona y puedo trabajar normalmente.','request','low')]
s=VoiceService()
for text,kind,priority in cases:
 r=s.classify_ticket(text)
 print(r['request_kind'],r['priority'],r['impact'],r['urgency'],flush=True)
 assert (r['request_kind'],r['priority'])==(kind,priority)
print('4 casos sintéticos verificados con AssemblyAI; no constituyen validación con participantes.')
