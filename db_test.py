import os
import mysql.connector
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_database_connection():
    """Prueba la conexión a la base de datos y verifica tablas y datos."""
    print("==== Test de conexión a la base de datos ====")
    
    # Configuración de la conexión
    config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'ti_management')
    }
    
    print(f"Intentando conectar a MySQL en {config['host']} con usuario {config['user']}")
    
    try:
        # Intentar conectar
        conn = mysql.connector.connect(**config)
        print("✅ Conexión a la base de datos exitosa!")
        
        # Verificar tablas
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print(f"\nTablas en la base de datos ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Verificar usuario admin
        cursor.execute("SELECT id, name, email, role FROM users WHERE email = 'admin@example.com'")
        admin_user = cursor.fetchone()
        
        if admin_user:
            print("\n✅ Usuario administrador encontrado:")
            print(f"  ID: {admin_user[0]}")
            print(f"  Nombre: {admin_user[1]}")
            print(f"  Email: {admin_user[2]}")
            print(f"  Rol: {admin_user[3]}")
        else:
            print("\n❌ Usuario administrador NO encontrado")
        
        # Verificar otros usuarios
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"\nTotal de usuarios en la base de datos: {user_count}")
        
        # Verificar activos
        cursor.execute("SELECT COUNT(*) FROM assets")
        asset_count = cursor.fetchone()[0]
        print(f"Total de activos en la base de datos: {asset_count}")
        
        # Verificar tickets
        cursor.execute("SELECT COUNT(*) FROM tickets")
        ticket_count = cursor.fetchone()[0]
        print(f"Total de tickets en la base de datos: {ticket_count}")
        
        # Cerrar conexión
        cursor.close()
        conn.close()
        print("\n✅ Test completado exitosamente")
        
    except mysql.connector.Error as err:
        print(f"\n❌ Error al conectar a la base de datos: {err}")
        
        # Sugerencias para solucionar el problema
        print("\nPosibles soluciones:")
        print("1. Asegúrate de que WAMP Server o XAMPP esté en ejecución")
        print("2. Verifica que las credenciales en el archivo .env sean correctas")
        print("3. Comprueba que la base de datos existe (ejecuta: python scripts/init_db.py)")
        print("4. Verifica que el usuario tenga permisos para acceder a la base de datos")

if __name__ == "__main__":
    test_database_connection()