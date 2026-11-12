# Sistema de Gestion TI

Aplicación Flask con MySQL local o PostgreSQL de Supabase para usuarios, inventario, tickets, comentarios y mediciones. Despliegue en Vercel: [instrucciones y migración](DEPLOY.md).

## Flujo simplificado por áreas

- **Superadministrador:** crea, edita, activa y desactiva áreas; administra usuarios y asigna su área y rol; consulta todos los pedidos y reportes.
- **Administrador de TI:** recibe las solicitudes de todas las áreas, asigna integrantes activos de TI y gestiona el inventario y la atención.
- **Técnico de TI:** consulta las solicitudes recibidas y registra su atención, respuesta y resolución.
- **Responsable de área:** consulta los pedidos e incidencias de su área y registra nuevas solicitudes.
- **Solicitante:** registra y consulta sus propios pedidos e incidencias, por formulario o voz, y agrega comentarios.

El destino es siempre TI. El área de origen se obtiene del usuario autenticado; el superadministrador también puede registrar una solicitud en representación de otra área. El formulario distingue pedidos de incidencias y el canal de voz utiliza el mismo flujo. Los cambios de estado se registran en los comentarios. Resolver o cerrar desde la interfaz requiere una respuesta de TI.

La migración `scripts/migrate_areas.py` conserva los registros anteriores, los vincula inicialmente a TI y convierte la primera cuenta administradora en superadministrador, sin cambiar su contraseña. Se ejecuta desde `INICIAR.ps1` y puede repetirse. Cada usuario debe tener un área activa; TI no puede desactivarse. Desactivar otra área conserva su historial y bloquea las sesiones de sus integrantes hasta reactivarla. Los cambios de rol se aplican a las sesiones abiertas.

Verificación del flujo completo, con áreas y usuarios temporales que se eliminan al finalizar:

```powershell
.venv\Scripts\python.exe scripts/verify_area_workflow.py
```

La prueba usa MySQL real y simula únicamente la transcripción de voz; no envía correo ni llama a AssemblyAI. La transcripción real y el micrófono requieren validación independiente.

## Temporizadores, notificaciones y resultados cuantitativos

Los avisos descartables, incluidos los errores de acceso, se cierran a los cinco segundos. La campana recibe notificaciones internas de nuevas solicitudes, asignaciones, cambios de estado, respuestas y comentarios. Los avisos se conservan en MySQL y se marcan como leídos al abrirlos. Se respeta el alcance de cada usuario y área.

El cronómetro empieza en la primera interacción del formulario o al iniciar la grabación. Una identificación de intento vinculada al usuario registra el inicio en el servidor. El tiempo total llega hasta la creación confirmada e incluye pausas, envío, transcripción y guardado. Se separan preparación/envío y procesamiento. Reenviar un intento ya exitoso no crea otro reporte; los intentos fallidos, abandonados o pendientes se muestran por separado. Tras dos horas sin envío se considera abandonado. Los registros antiguos no reciben tiempos inventados.

El dashboard y la campana consultan los cambios cada cinco segundos mientras la pestaña está visible. Los filtros por fechas (horario de Lima) y tipo de solicitud afectan las estadísticas y exportaciones. Se muestran tamaño de muestra, promedio, mediana, percentil 90, desviación estándar, extremos, tasa de éxito, fases y evolución diaria por canal. La reducción es `(promedio manual - promedio voz) / promedio manual × 100`: puede ser negativa. La tasa de éxito usa éxitos divididos entre éxitos más fallos. Las comparaciones son observacionales; la complejidad, el tipo y las pausas pueden diferir. No se presenta superioridad automática de un canal.

Cada gráfico permite descargar PNG de 3840 × 2160 píxeles o SVG vectorial. Los datos se exportan a CSV; el informe con indicadores, metodología, mediciones y siete gráficos se descarga como HTML o se abre para imprimir/guardar como PDF desde el navegador.

```powershell
.venv\Scripts\python.exe scripts/verify_insights.py
.venv\Scripts\python.exe scripts/verify_browser_insights.py
```

La primera prueba verifica métricas, permisos, avisos y archivos con datos temporales que elimina al terminar. La segunda usa Chrome instalado en un perfil aislado, comprueba el cronómetro, la descarga PNG 4K, los gráficos, el diseño móvil y el cierre de avisos. Usa micrófono y respuesta de voz simulados, sin consumir AssemblyAI ni utilizar el perfil del navegador del usuario. Sus evidencias quedan en `.runtime/browser-insights`.

## Acceso local

- URL: http://127.0.0.1:5000
- Usuario inicial: admin@example.com
- Clave inicial: admin123
- MySQL: 127.0.0.1:3307, base ti_management.

## Iniciar en este equipo

Desde PowerShell en la carpeta del proyecto:

```powershell
.\INICIAR.ps1
```

El script inicia la instancia MySQL del proyecto cuando hace falta y sirve Flask mediante Waitress. Si el puerto web ya esta ocupado, informa la URL. La ruta del ejecutable MySQL instalado en Wamp se encuentra en INICIAR.ps1. Los procesos se limitan a la interfaz local.

Los datos locales persistentes están en `.runtime/mysql`; no borrar esa carpeta. Los registros están en `.runtime/logs`. Las credenciales se guardan en `.env` y en archivos privados de `.runtime`, excluidos de Git. En la nube, los datos quedan en Supabase y las claves se configuran como variables privadas en Vercel.

## Entorno y dependencias

Python 3.12 esta instalado dentro de `.python` y el entorno virtual en `.venv`.

```powershell
$env:UV_CACHE_DIR="$PWD\.cache\uv"
$env:UV_PYTHON_INSTALL_DIR="$PWD\.python"
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

Para otra instalacion de MySQL, ajustar DB_HOST, DB_PORT, DB_USER, DB_PASSWORD y DB_NAME en .env. El usuario necesita permisos para crear las tablas durante la inicializacion:

```powershell
.venv\Scripts\python.exe scripts/init_db.py
```

CREATE_SAMPLE_DATA=False evita agregar datos ficticios al inicializar.

## Verificacion

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe scripts/smoke_test.py
```

La prueba realiza 36 comprobaciones contra la base real: autenticacion, rutas, altas, ediciones, comentarios, monitoreo y desactivacion. Elimina los registros creados por la prueba y deja el resultado en .runtime/smoke-results.json. Tambien se verificaron peticiones HTTP reales al servidor con altas de activos, tickets, metricas y edicion de tickets.

## Alcance de integraciones

La transcripcion de voz requiere una clave AssemblyAI valida y conectividad. No se verifico una transcripcion externa ni el microfono. El correo requiere configuracion SMTP real; sin ella no se envia correo. El monitoreo se registra manualmente: no hay agente de telemetria instalado. Las estimaciones de fallos usan reglas cuando no existe un modelo entrenado. El control del navegador integrado no estuvo disponible, por lo que no se realizo una comprobacion visual.
