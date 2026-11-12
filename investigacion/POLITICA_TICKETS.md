# Política de tickets y roles — preparación local 1.1.0

- Superadministrador: gestiona áreas y usuarios; no asigna responsables ni modifica tickets como excepción al encargado.
- Encargado (manager): uno activo por área. Ve solicitudes de su área y tickets destinados a ella. Solo puede asignar trabajadores activos del área de destino que dirige.
- Trabajador (user): crea solicitudes, consulta las suyas y atiende las que tiene asignadas en su área. Los antiguos admin/technician conservan su identidad histórica pero no tienen privilegios de encargado. No se designa un encargado automáticamente.
- Después de la primera asignación, prioridad y tipo quedan bloqueados permanentemente, incluso si se retira el responsable. Al resolver o cerrar, no se permite editar ni añadir comentarios. Resolver/cerrar requiere registrar una respuesta.
- La migración aplica un bloqueo en base de datos y unicidad del encargado, además de las verificaciones del controlador. Si existen varios encargados activos, hay que elegir quién continúa antes de migrar; no se convierten automáticamente.

## Clasificación de voz
AssemblyAI transcribe. Su LLM Gateway interpreta tipo, impacto, urgencia y justificación mediante JSON validado por el servidor. La aplicación calcula la prioridad con una matriz reproducible. No basta con decir urgente.

| Impacto | Planificado/sin impedimento | Puede trabajar con limitaciones | Trabajo bloqueado sin alternativa |
|---|---|---|---|
| Individual | Baja | Media | Alta |
| Un área | Media | Alta | Alta |
| Varias áreas/toda la entidad | Media | Alta | Crítica |

Incidencia: fallo o degradación de un servicio existente. Pedido: alta, equipo, instalación, acceso, información o cambio sin fallo existente. Si hay información insuficiente o solicitudes mezcladas, pide aclaración y no inventa un ticket. El audio autorizado del intento fallido sigue conservado.

Modelo configurado mediante ASSEMBLYAI_CLASSIFIER_MODEL, predeterminado qwen3.5-4b-32k-fast. La justificación y el modelo configurado se registran como comentario inicial; la versión del software y el audio quedan vinculados al intento. No hay afirmación de exactitud clínica/estadística ni evaluación humana terminada.

## Verificación de 2026-11-11
- PostgreSQL aislado: 22 comprobaciones nuevas de permisos/bloqueos/matriz y 31 comprobaciones de conservación de audio, satisfactorias. Se simuló la salida del proveedor en los casos de audio.
- Migración PostgreSQL ejecutada dos veces para verificar repetición sin alteraciones indebidas.
- Prueba real: el modelo Gemini configurado rechazó el acceso. Se comprobó acceso a qwen3.5-4b-32k-fast y se adaptó la petición porque ese modelo no admite response_format. Cuatro casos sintéticos reales pasaron: incidencia individual bloqueante/alta, instalación para un área/media, interrupción institucional/crítica y pedido individual planificado/baja pese a decir urgente. Esto no reemplaza pruebas con participantes ni acredita exactitud general. No se modificó facturación.
- Migración MySQL preparada, sin ejecución contra el MySQL local detenido.
- Confirmado por el usuario: todas las áreas envían pedidos e incidencias a TI. El enrutamiento existente se conserva; únicamente el encargado de TI asigna responsables para atenderlos.
- Sin cambios en GitHub ni producción. Servidor normal local permanece detenido. Pendiente plazo de conservación de audio acordado para estudio.

Fuentes: https://www.assemblyai.com/docs/llm-gateway/structured-outputs
