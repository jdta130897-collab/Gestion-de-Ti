# Preparación de la evaluación actual

Estado al 11 de noviembre de 2026. Trabajo local, anterior al levantamiento de
observaciones. Ninguna observación editorial se declara resuelta en esta etapa.

## Decisiones del autor

- El artículo corregido representará la versión actual del software.
- Explicar expresamente los elementos conservados del prototipo anterior.
- Realizar pruebas nuevas; participantes previstos: cuatro personas o más.
- No presentar las pruebas técnicas automatizadas como evaluación de usuarios.
- No publicar cambios en GitHub sin consultar al autor.
- Resolver cada observación completamente antes de continuar con la siguiente.

## Entorno de desarrollo comprobado

| Elemento | Valor observado |
| --- | --- |
| Equipo | Alienware m16 R2 |
| Procesador | Intel Core Ultra 9 185H |
| Núcleos / procesadores lógicos | 16 / 22 |
| Memoria física visible al sistema | 31,52 GiB |
| Sistema operativo | Microsoft Windows 11 Pro, 64 bits |
| Versión / compilación | 10.0.26300 / 26300 |
| Python del proyecto | 3.12.13 |
| Flask declarado en dependencias | 3.1.2 |
| SDK AssemblyAI declarado | 1.8.2 |
| Base de datos de producción consultada | PostgreSQL 17.11, Supabase |
| Alojamiento de producción | Vercel |

Las versiones declaradas en requirements.txt no equivalen por sí mismas a una
medición del entorno remoto. Este equipo es el entorno de desarrollo; los
dispositivos de los participantes y la ejecución remota deben documentarse por
separado al realizar las pruebas. No atribuirle las especificaciones del servidor.

## Auditoría del audio

`VoiceService.save_temp_audio` escribe mediante `NamedTemporaryFile` en el
directorio temporal del sistema. `transcribe_audio` envía ese archivo al proveedor.
`TicketController.create_ticket_from_audio` elimina el archivo en `finally`, tanto
si termina correctamente como si falla. La transcripción se procesa después de
detener la grabación; no es transcripción continua en streaming.

La consulta de information_schema en Supabase no encontró columnas o tablas con
audio ni versión. No hay un archivo de grabaciones propio de la aplicación.
La retención del proveedor externo no se ha auditado y no se afirma que sus copias
se eliminen al eliminar el archivo temporal de Flask.

Existe `temp_audio_original.webm` en el directorio local. Su existencia aislada no
demuestra identidad del participante, ticket, fecha de captura, consentimiento ni
relación con una evaluación; no se incorpora como evidencia experimental.

## Condiciones previas a la recogida de datos

Preparar conservación privada de audios y su asociación a participante codificado,
intento, ticket cuando exista, versión, fecha, formato y resultado. Definir acceso,
consentimiento, plazo de conservación y eliminación antes de grabar participantes.
Los fallos también deben poder documentarse; conservar solo éxitos sesgaría la
evaluación. La conservación efectiva debe verificarse antes de comenzar.

Actualización local: archivo privado implementado en la base de datos, con prueba
de bytes y SHA-256, permisos por propietario/superadministrador y conservación de
fallos. Véase `CONSERVACION_AUDIO.md`. Sigue pendiente acordar retención y autorizar
publicación; la auditoría del estado anterior de producción se conserva arriba.

Registrar la versión en cada nuevo intento y no asignar versiones retrospectivas
sin evidencia. Congelar una versión para la campaña y documentar cualquier cambio.

La cantidad concreta de tareas, escenarios, repeticiones, criterios de validez y
participantes finales está pendiente de definición con el autor. Cuatro o más es
una previsión de reclutamiento, no evidencia de suficiencia estadística.

## Publicación

Identificación local preparada: 1.1.0. Pendiente consultar al autor y, si autoriza,
sincronizar repositorio y despliegue, comprobar `/healthz` y registrar el commit
publicado. No comenzar todavía la evaluación ni modificar el manuscrito.
