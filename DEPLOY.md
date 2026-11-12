# Despliegue en Vercel y Supabase

La aplicación Flask conserva su interfaz y sus roles. En la nube usa PostgreSQL de
Supabase; localmente puede seguir usando MySQL si `DATABASE_URL` está vacía.

## Variables privadas en Vercel

- `DATABASE_URL`: URL del Transaction pooler de Supabase, puerto 6543, con `sslmode=require`.
- `SECRET_KEY`: valor aleatorio privado, estable entre despliegues.
- `ASSEMBLYAI_API_KEY`: clave del servicio de transcripción, solo en el servidor.
- `SESSION_COOKIE_SECURE=True` y `ENABLE_REGISTRATION=False`.

No subir `.env`, copias de la base ni claves al repositorio. La conexión al pooler
desactiva los prepared statements. Los recursos estáticos se copian a
`public/static` durante el build; las rutas `/static/...` mantienen su funcionamiento.

## Base de datos

Aplicar `python scripts/migrate_postgres.py` con `DATABASE_URL` configurada. Las
migraciones son aditivas y no generan estadísticas ni usuarios ficticios.

Para conservar las cuentas y registros locales, ejecutar una única vez
`python scripts/migrate_mysql_to_supabase.py`: toma `DB_*` del MySQL de origen y
`DATABASE_URL` del destino. Copia todas las tablas en una transacción, conserva
identificadores y hashes de contraseñas, comprueba el número de filas y ajusta las
secuencias. Se niega a copiar sobre un destino que ya tenga registros.

Las tablas tienen RLS activado sin acceso directo para clientes públicos. Flask
usa una conexión privada y aplica los permisos del usuario y del área en cada
solicitud. No se necesita publicar una service role key en el navegador.

## Publicación y comprobación

Importar el repositorio en Vercel o ejecutar `vercel --prod`. El entrypoint es
`app.py`; el build ejecuta `scripts/build_vercel.py`. `/healthz` comprueba la
conexión sin revelar credenciales. Verificar inicio de sesión, registro manual,
voz, notificaciones, dashboard y descargas en la URL HTTPS publicada.

La grabación usa Opus a 32 kbps y termina como máximo a los 3 minutos. El servidor
limita la carga a 4 MB para respetar el límite de 4,5 MB de Vercel; la función tiene
300 segundos de duración máxima. La transcripción depende de AssemblyAI y de su
disponibilidad/cuota. Los audios son temporales y se eliminan tras la solicitud;
los reportes, comentarios, notificaciones y mediciones quedan en Supabase.

En Vercel la configuración del servidor se cambia mediante variables de entorno,
porque el sistema de archivos de las funciones no es un almacenamiento persistente.
El panel sigue actualizando sus estadísticas cada 5 segundos mientras está abierto.

## Pruebas locales

`python scripts/verify_area_workflow.py` y `python scripts/verify_insights.py`
verifican permisos, aislamiento por área, registros y comparativas. Usan fixtures
temporales y transcripción simulada; no prueban el proveedor real de voz. Pueden
ejecutarse con MySQL o con una base PostgreSQL de pruebas.
