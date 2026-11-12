import mysql.connector
import os
import sys
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Añadir el directorio raíz al path para poder importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()


def init_database():
    """Inicializa la base de datos y crea las tablas necesarias."""
    print("=== Inicializando base de datos del Sistema de Gestión TI ===")
    
    # Conectar a MySQL sin seleccionar base de datos
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "")
        )
        print("✅ Conexión a MySQL establecida")
    except mysql.connector.Error as err:
        print(f"❌ Error al conectar a MySQL: {err}")
        return False
    
    cursor = conn.cursor(buffered=True)
    
    # Crear base de datos si no existe
    db_name = os.getenv("DB_NAME", "ti_management")
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {db_name}")
        print(f"✅ Base de datos '{db_name}' creada/seleccionada correctamente")
    except mysql.connector.Error as err:
        print(f"❌ Error al crear/seleccionar base de datos: {err}")
        cursor.close()
        conn.close()
        return False
    
    # Crear tablas
    tables = {}
    
    # Tabla de usuarios
    tables['users'] = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('admin', 'manager', 'technician', 'user') NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        ) ENGINE=InnoDB
    """
    
    # Tabla de activos
    tables['assets'] = """
        CREATE TABLE IF NOT EXISTS assets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            type VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL,
            purchase_date DATE NOT NULL,
            assigned_to INT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB
    """
    
    # Tabla de tickets
    tables['tickets'] = """
        CREATE TABLE IF NOT EXISTS tickets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            status ENUM('open', 'in_progress', 'resolved', 'closed') NOT NULL,
            priority ENUM('low', 'medium', 'high', 'critical') NOT NULL,
            created_by INT NOT NULL,
            assigned_to INT,
            related_asset INT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            resolved_at DATETIME,
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (related_asset) REFERENCES assets(id) ON DELETE SET NULL
        ) ENGINE=InnoDB
    """
    
    # Tabla de comentarios de tickets
    tables['ticket_comments'] = """
        CREATE TABLE IF NOT EXISTS ticket_comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ticket_id INT NOT NULL,
            user_id INT NOT NULL,
            comment TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        ) ENGINE=InnoDB
    """
    
    # Tabla de monitoreo
    tables['monitoring_data'] = """
        CREATE TABLE IF NOT EXISTS monitoring_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            asset_id INT NOT NULL,
            metric_name VARCHAR(50) NOT NULL,
            metric_value FLOAT NOT NULL,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """
    
    # Tabla de API keys
    tables['api_keys'] = """
        CREATE TABLE IF NOT EXISTS api_keys (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            api_key VARCHAR(255) NOT NULL,
            expiry_date DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """
    
    # Crear todas las tablas
    for table_name, table_query in tables.items():
        try:
            cursor.execute(table_query)
            print(f"✅ Tabla '{table_name}' creada correctamente")
        except mysql.connector.Error as err:
            print(f"❌ Error al crear tabla '{table_name}': {err}")
    
    # Crear usuario admin por defecto si no existe
    try:
        cursor.execute("SELECT id FROM users WHERE email = 'admin@example.com'")
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            # Crear usuario admin
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            admin_password_hash = generate_password_hash("admin123")
            
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, ("Admin User", "admin@example.com", admin_password_hash, "admin", now, now))
            
            print("✅ Usuario administrador creado correctamente")
        else:
            print("ℹ️ Usuario administrador ya existe")
    except mysql.connector.Error as err:
        print(f"❌ Error al crear usuario admin: {err}")
    
    # Crear datos de ejemplo si se solicita
    if os.getenv("CREATE_SAMPLE_DATA", "False") == "True":
        try:
            create_sample_data(conn, cursor)
            print("✅ Datos de ejemplo creados correctamente")
        except Exception as err:
            print(f"❌ Error al crear datos de ejemplo: {err}")
    
    # Confirmar cambios y cerrar conexión
    conn.commit()
    cursor.close()
    conn.close()
    
    print("=== Base de datos inicializada correctamente ===")
    return True


def create_sample_data(conn, cursor):
    """Crea datos de ejemplo para pruebas."""
    now = datetime.now()
    
    # Crear algunos usuarios de ejemplo
    users = [
        ("María García", "maria@example.com", generate_password_hash("password123"), "manager"),
        ("Carlos Rodríguez", "carlos@example.com", generate_password_hash("password123"), "technician"),
        ("Ana Martínez", "ana@example.com", generate_password_hash("password123"), "user"),
        ("Juan López", "juan@example.com", generate_password_hash("password123"), "technician"),
        ("Laura Sánchez", "laura@example.com", generate_password_hash("password123"), "user")
    ]
    
    print("Creando usuarios de ejemplo...")
    for user in users:
        try:
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user[0], user[1], user[2], user[3], now, now))
            print(f"  - Usuario: {user[0]} ({user[3]})")
        except mysql.connector.Error as err:
            if err.errno == 1062:  # Error de duplicado
                print(f"  - Usuario {user[1]} ya existe, omitiendo...")
            else:
                print(f"  - Error al crear usuario {user[0]}: {err}")
    
    # Obtener IDs de usuarios
    cursor.execute("SELECT id, role FROM users")
    users_data = cursor.fetchall()
    user_ids = {}
    for user_id, role in users_data:
        if role not in user_ids:
            user_ids[role] = []
        user_ids[role].append(user_id)
    
    # Crear algunos activos de ejemplo
    assets = [
        ("Servidor Principal", "hardware", "active", (now - timedelta(days=365)).date(), 
         random.choice(user_ids.get("technician", [None]))),
        ("Switch de Red", "network", "active", (now - timedelta(days=180)).date(), None),
        ("Software Contabilidad", "software", "active", (now - timedelta(days=90)).date(), 
         random.choice(user_ids.get("user", [None]))),
        ("Impresora Central", "peripheral", "maintenance", (now - timedelta(days=730)).date(), None),
        ("Laptop Desarrollo", "hardware", "active", (now - timedelta(days=150)).date(), 
         random.choice(user_ids.get("technician", [None]))),
        ("Router Oficina 1", "network", "active", (now - timedelta(days=120)).date(), None),
        ("Licencia Office 365", "software", "active", (now - timedelta(days=30)).date(), 
         random.choice(user_ids.get("user", [None]))),
        ("Escáner Documentos", "peripheral", "active", (now - timedelta(days=200)).date(), 
         random.choice(user_ids.get("user", [None]))),
        ("Servidor Backup", "hardware", "maintenance", (now - timedelta(days=500)).date(), None),
        ("Firewall", "network", "active", (now - timedelta(days=100)).date(), None)
    ]
    
    print("Creando activos de ejemplo...")
    for asset in assets:
        cursor.execute("""
            INSERT INTO assets (name, type, status, purchase_date, assigned_to, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (asset[0], asset[1], asset[2], asset[3], asset[4], now, now))
        print(f"  - Activo: {asset[0]} ({asset[1]})")
    
    # Obtener IDs de activos
    cursor.execute("SELECT id, name FROM assets")
    assets_data = cursor.fetchall()
    asset_ids = {name: asset_id for asset_id, name in assets_data}
    
    # Crear algunos tickets de ejemplo
    tickets = [
        ("Error en servidor", "El servidor principal muestra errores de memoria RAM. Se reinicia constantemente.", 
         "open", "high", random.choice(user_ids.get("manager", [user_ids.get("admin", [1])[0]])), 
         random.choice(user_ids.get("technician", [None])), asset_ids.get("Servidor Principal")),
        
        ("Actualizar software", "Necesitamos actualizar el software de contabilidad a la última versión.", 
         "in_progress", "medium", random.choice(user_ids.get("user", [user_ids.get("admin", [1])[0]])), 
         random.choice(user_ids.get("technician", [None])), asset_ids.get("Software Contabilidad")),
        
        ("Impresora no funciona", "La impresora central no imprime documentos. Muestra error de tóner.", 
         "resolved", "medium", random.choice(user_ids.get("user", [user_ids.get("admin", [1])[0]])), 
         random.choice(user_ids.get("technician", [None])), asset_ids.get("Impresora Central")),
        
        ("Configurar nuevo router", "Se necesita configurar el nuevo router para la oficina 1.", 
         "open", "low", random.choice(user_ids.get("manager", [user_ids.get("admin", [1])[0]])), 
         None, asset_ids.get("Router Oficina 1")),
        
        ("Problemas de conexión", "Hay problemas de conexión a internet intermitentes en toda la red.", 
         "in_progress", "critical", random.choice(user_ids.get("user", [user_ids.get("admin", [1])[0]])), 
         random.choice(user_ids.get("technician", [None])), asset_ids.get("Switch de Red")),
        
        ("Solicitud de licencias", "Necesitamos 5 licencias adicionales de Office 365.", 
         "closed", "low", random.choice(user_ids.get("user", [user_ids.get("admin", [1])[0]])), 
         random.choice(user_ids.get("manager", [None])), asset_ids.get("Licencia Office 365")),
        
        ("Falla en servidor de backup", "El servidor de backup no está realizando las copias programadas.", 
         "open", "high", random.choice(user_ids.get("technician", [user_ids.get("admin", [1])[0]])), 
         random.choice(user_ids.get("technician", [None])), asset_ids.get("Servidor Backup"))
    ]
    
    print("Creando tickets de ejemplo...")
    for ticket in tickets:
        ticket_time = now - timedelta(days=random.randint(1, 30), 
                                      hours=random.randint(0, 23), 
                                      minutes=random.randint(0, 59))
        resolved_at = now if ticket[2] == "resolved" else None
        
        cursor.execute("""
            INSERT INTO tickets (title, description, status, priority, created_by, assigned_to, 
                                related_asset, created_at, updated_at, resolved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (ticket[0], ticket[1], ticket[2], ticket[3], ticket[4], ticket[5], ticket[6], 
             ticket_time, now, resolved_at))
        print(f"  - Ticket: {ticket[0]} ({ticket[3]} prioridad, {ticket[2]})")
    
    # Obtener IDs de tickets
    cursor.execute("SELECT id, title FROM tickets")
    ticket_data = cursor.fetchall()
    ticket_ids = {title: ticket_id for ticket_id, title in ticket_data}
    
    # Crear algunos comentarios de tickets
    comments = [
        (ticket_ids.get("Error en servidor"), 
         random.choice(user_ids.get("technician", [1])), 
         "Estoy revisando el servidor. Parece que hay un problema con los módulos de RAM.", 
         now - timedelta(hours=random.randint(1, 48))),
        
        (ticket_ids.get("Error en servidor"), 
         random.choice(user_ids.get("manager", [1])), 
         "Por favor mantennos informados del estado. Es un equipo crítico.", 
         now - timedelta(hours=random.randint(1, 24))),
        
        (ticket_ids.get("Actualizar software"), 
         random.choice(user_ids.get("technician", [1])), 
         "He comenzado la actualización. Esto tomará aproximadamente 2 horas.", 
         now - timedelta(hours=random.randint(1, 24))),
        
        (ticket_ids.get("Impresora no funciona"), 
         random.choice(user_ids.get("technician", [1])), 
         "He reemplazado el tóner y realizado mantenimiento. La impresora funciona correctamente ahora.", 
         now - timedelta(hours=random.randint(1, 12))),
        
        (ticket_ids.get("Problemas de conexión"), 
         random.choice(user_ids.get("technician", [1])), 
         "Estoy analizando el tráfico de red para identificar la causa de los problemas.", 
         now - timedelta(hours=random.randint(1, 6))),
        
        (ticket_ids.get("Problemas de conexión"), 
         random.choice(user_ids.get("user", [1])), 
         "El problema persiste. Ahora la conexión es más lenta que antes.", 
         now - timedelta(hours=random.randint(1, 3)))
    ]
    
    print("Creando comentarios de tickets...")
    for comment in comments:
        cursor.execute("""
            INSERT INTO ticket_comments (ticket_id, user_id, comment, created_at)
            VALUES (%s, %s, %s, %s)
        """, comment)
    
    # Crear algunos datos de monitoreo
    print("Creando datos de monitoreo...")
    for asset_id in asset_ids.values():
        # Generar datos para los últimos 7 días
        for day in range(7):
            for hour in range(0, 24, 4):  # Cada 4 horas
                # CPU usage
                cursor.execute("""
                    INSERT INTO monitoring_data (asset_id, metric_name, metric_value, timestamp)
                    VALUES (%s, %s, %s, %s)
                """, (asset_id, "cpu_usage", random.uniform(10, 95), 
                     now - timedelta(days=day, hours=hour)))
                
                # Memory usage
                cursor.execute("""
                    INSERT INTO monitoring_data (asset_id, metric_name, metric_value, timestamp)
                    VALUES (%s, %s, %s, %s)
                """, (asset_id, "memory_usage", random.uniform(20, 90), 
                     now - timedelta(days=day, hours=hour)))
                
                # Disk usage
                cursor.execute("""
                    INSERT INTO monitoring_data (asset_id, metric_name, metric_value, timestamp)
                    VALUES (%s, %s, %s, %s)
                """, (asset_id, "disk_usage", random.uniform(30, 85), 
                     now - timedelta(days=day, hours=hour)))
                
                # Temperature (solo para hardware)
                asset_cursor = conn.cursor(buffered=True)
                asset_cursor.execute("SELECT type FROM assets WHERE id = %s", (asset_id,))
                asset_type = asset_cursor.fetchone()[0]
                asset_cursor.close()
                
                if asset_type in ["hardware", "network"]:
                    cursor.execute("""
                        INSERT INTO monitoring_data (asset_id, metric_name, metric_value, timestamp)
                        VALUES (%s, %s, %s, %s)
                    """, (asset_id, "temperature", random.uniform(35, 75), 
                         now - timedelta(days=day, hours=hour)))
    
    # Confirmar cambios
    conn.commit()
    print("Datos de ejemplo creados con éxito")


if __name__ == "__main__":
    if init_database():
        from scripts.migrate_areas import migrate
        migrate()
