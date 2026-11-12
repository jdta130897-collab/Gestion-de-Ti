# Historial de versiones

## 1.1.0 — publicación autorizada el 11 de noviembre de 2026

Versión actual seleccionada para la nueva evaluación del artículo. Identificación
centralizada en `VERSION`, visible en la interfaz y consultable en `/healthz`.
Publicación autorizada por el autor.

Capacidades de la versión actual: gestión de áreas y roles, pedidos e incidencias,
registro manual y por voz, vista previa superpuesta, interfaz en español,
notificaciones, temporizadores, métricas comparativas, exportaciones, adaptación
móvil y conexión de producción con PostgreSQL de Supabase y Vercel.

Se mantienen del prototipo: Flask, AssemblyAI, captura mediante inicio y detención,
transcripción posterior a la grabación,
categoría incluida en la descripción y MySQL como alternativa local.

Conservación privada incorporada: audio original en PostgreSQL BYTEA
(o LONGBLOB con MySQL), SHA-256, participante codificado, intento, consentimiento,
transcripción, resultado, versión y commit cuando esté disponible. Incluye fallos
y pantalla privada de descarga y eliminación. La copia temporal se sigue borrando.
Solo el propietario y el superadministrador tienen acceso a los audios.

La versión se registra también en las nuevas mediciones manuales. Los registros
históricos sin versión conservan ese estado. El plazo de retención definitivo
está pendiente de decisión del autor; no se realiza eliminación automática.

## Publicación previa sin identificación de revisión

La interfaz mostraba 1.0.0. Último commit publicado verificado antes de preparar
1.1.0: `5afd2b6` (corrección del envío manual). No se considera que esta etiqueta
distinga adecuadamente la versión original del artículo y todas sus mejoras.

Clasificación automática mediante AssemblyAI LLM Gateway (Qwen), validación de JSON
y matriz de prioridades. No exige aclaraciones; impacto o urgencia desconocidos
reciben prioridad media inicial. Gestión y seguimiento exclusivos de TI,
asignación por su encargado y bloqueo de clasificación desde la primera asignación.
Tickets resueltos o cerrados sin edición.
