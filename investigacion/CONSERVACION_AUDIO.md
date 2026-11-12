# Archivo privado de grabaciones

Implementación local preparada para 1.1.0. No publicada ni aplicada al Supabase
de producción. El plazo de conservación está pendiente de confirmación del autor.

## Ubicación y relaciones

El archivo original se copia a `voice_recordings.audio_data`: BYTEA en PostgreSQL
y LONGBLOB en MySQL. En producción prevista estará dentro de la base privada de
Supabase, no en Supabase Storage ni en un bucket público. Se eligió esta solución
para el piloto pequeño y audios de hasta 3,9 MB, aprovechando la conexión privada
ya disponible. El crecimiento de volumen requerirá revisar almacenamiento y cuota.

Cada grabación conserva ID, intento, propietario, participante codificado,
ticket cuando existe, versión, commit disponible, fecha UTC, autorización,
tipo, tamaño, SHA-256, transcripción y resultado. Un intento admite un solo audio.
El código es estable por cuenta; para representar personas distintas, cada
participante debe usar una cuenta propia. No equivale a anonimización irreversible.

Las mediciones nuevas también guardan versión y commit. Los datos antiguos no se
reetiquetan ni se recuperan audios eliminados por la implementación anterior.
El CSV de mediciones agrega versión, participante codificado y commit disponible.

## Flujo

1. El usuario autoriza la conservación antes de iniciar el micrófono.
2. El servidor valida la autorización y el intento de esa misma cuenta.
3. Archiva los bytes originales antes de llamar al transcriptor.
4. Procesa la transcripción y crea el ticket si hay contenido válido.
5. Registra éxito o fallo en el archivo; un fallo no descarta el audio original.
6. Elimina la copia temporal, conservando la copia en base de datos.

Si no puede archivar el audio, se rechaza el proceso en lugar de crear un ticket
de investigación sin su evidencia. Archivos vacíos o excesivos no se archivan.
Si la función se interrumpe de forma abrupta, un audio puede quedar en estado
procesando; no se convierte automáticamente en éxito ni se inventa su resultado.

## Acceso y eliminación

`/recordings` presenta los audios del usuario; el superadministrador ve todos.
La descarga exige sesión y propietario o superadministrador, devuelve adjunto
y prohíbe caché pública. No hay una URL pública de almacenamiento.
Un técnico o responsable de área no recibe permisos de audio por poder ver tickets.
Las tablas PostgreSQL tienen RLS activado sin políticas para clientes públicos.

Propietario y superadministrador pueden eliminar un audio. Se conservan el ticket
y las mediciones. Eliminar la cuenta elimina sus grabaciones y código vinculados.
La eliminación en la base activa no acredita eliminación inmediata de backups
del proveedor. Tampoco define la política de retención propia de AssemblyAI.

La autorización de conservación de la aplicación no sustituye el consentimiento
informado específico de la investigación. Definir finalidad, plazo y procedimiento
de retiro antes de reclutar participantes. El plazo y cualquier purga automática
quedan pendientes; no se ha asumido una duración ni se ha programado borrado.

## Verificación y publicación pendiente

Pruebas locales: `scripts/verify_private_audio.py`, con WAV de silencio generado
para fixtures y transcripción simulada, sin llamadas externas a AssemblyAI.
Se verifican bytes, hash, relaciones, versiones, permisos, fallos, reintentos y
eliminación; los fixtures se limpian al terminar. No son resultados de participantes.

Antes de publicar: confirmar retención, autorizar publicación, aplicar migraciones
de producción, desplegar la versión, probar por HTTPS y verificar almacenamiento
con micrófono real. No iniciar la campaña de evaluación antes de esas verificaciones.
