from datetime import datetime
from config.database import Database

class BaseModel:
    """Clase base para todos los modelos."""
    db = Database()
    table_name = None
    
    @classmethod
    def find_all(cls):
        """Encuentra todos los registros de la tabla."""
        query = f"SELECT * FROM {cls.table_name}"
        return cls.db.execute_query(query)
    
    @classmethod
    def find_by_id(cls, id):
        """Encuentra un registro por su ID."""
        query = f"SELECT * FROM {cls.table_name} WHERE id = %s"
        result = cls.db.execute_query(query, (id,))
        return result[0] if result else None
    
    @classmethod
    def delete(cls, id):
        """Elimina un registro por su ID."""
        query = f"DELETE FROM {cls.table_name} WHERE id = %s"
        return cls.db.execute_update(query, (id,))


class Asset(BaseModel):
    """Modelo para gestionar activos de TI."""
    table_name = "assets"
    
    def __init__(self, db=None):
        """Inicializa el modelo con una conexión a la base de datos."""
        self.db = db if db else Database()
    
    def get_all(self):
        """Obtiene todos los activos."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = """
            SELECT a.*, u.name as assigned_to_name
            FROM assets a
            LEFT JOIN users u ON a.assigned_to = u.id
            ORDER BY a.name
            """
            
            cursor.execute(query)
            assets = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return {"status": "success", "data": assets}
        except Exception as e:
            print(f"Error al obtener activos: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_by_id(self, asset_id):
        """Obtiene un activo por su ID."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = """
            SELECT a.*, u.name as assigned_to_name
            FROM assets a
            LEFT JOIN users u ON a.assigned_to = u.id
            WHERE a.id = %s
            """
            
            cursor.execute(query, (asset_id,))
            asset = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if asset:
                return {"status": "success", "data": asset}
            else:
                return {"status": "error", "message": "Activo no encontrado"}
        except Exception as e:
            print(f"Error al obtener activo: {e}")
            return {"status": "error", "message": str(e)}
    
    def create(self, asset_data):
        """Crea un nuevo activo."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            query = """
            INSERT INTO assets (name, type, status, purchase_date, assigned_to, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Manejar el caso de assigned_to vacío
            assigned_to = asset_data.get('assigned_to')
            if assigned_to == '':
                assigned_to = None
            
            values = (
                asset_data.get('name'),
                asset_data.get('type'),
                asset_data.get('status'),
                asset_data.get('purchase_date'),
                assigned_to,
                now,
                now
            )
            
            cursor.execute(query, values)
            conn.commit()
            
            new_id = cursor.lastrowid
            
            cursor.close()
            conn.close()
            
            return {"status": "success", "message": "Activo creado correctamente", "id": new_id}
        except Exception as e:
            print(f"Error al crear activo: {e}")
            return {"status": "error", "message": str(e)}
    
    def update(self, asset_id, asset_data):
        """Actualiza un activo existente."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            query = """
            UPDATE assets
            SET name = %s, type = %s, status = %s, purchase_date = %s, assigned_to = %s, updated_at = %s
            WHERE id = %s
            """
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Manejar el caso de assigned_to vacío
            assigned_to = asset_data.get('assigned_to')
            if assigned_to == '':
                assigned_to = None
            
            values = (
                asset_data.get('name'),
                asset_data.get('type'),
                asset_data.get('status'),
                asset_data.get('purchase_date'),
                assigned_to,
                now,
                asset_id
            )
            
            cursor.execute(query, values)
            conn.commit()
            
            affected_rows = cursor.rowcount
            
            cursor.close()
            conn.close()
            
            if affected_rows > 0:
                return {"status": "success", "message": "Activo actualizado correctamente"}
            else:
                return {"status": "error", "message": "No se pudo actualizar el activo"}
        except Exception as e:
            print(f"Error al actualizar activo: {e}")
            return {"status": "error", "message": str(e)}
    
    def delete(self, asset_id):
        """Elimina un activo."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Primero verificar si el activo está relacionado con tickets
            check_query = """
            SELECT COUNT(*) FROM tickets WHERE related_asset = %s
            """
            
            cursor.execute(check_query, (asset_id,))
            count = cursor.fetchone()[0]
            
            if count > 0:
                cursor.close()
                conn.close()
                return {
                    "status": "error", 
                    "message": f"No se puede eliminar el activo porque está relacionado con {count} ticket(s)"
                }
            
            # Si no está relacionado, eliminar el activo
            delete_query = """
            DELETE FROM assets WHERE id = %s
            """
            
            cursor.execute(delete_query, (asset_id,))
            conn.commit()
            
            affected_rows = cursor.rowcount
            
            cursor.close()
            conn.close()
            
            if affected_rows > 0:
                return {"status": "success", "message": "Activo eliminado correctamente"}
            else:
                return {"status": "error", "message": "No se pudo eliminar el activo"}
        except Exception as e:
            print(f"Error al eliminar activo: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_types(self):
        """Obtiene los tipos de activos disponibles."""
        return [
            {"id": "hardware", "name": "Hardware"},
            {"id": "software", "name": "Software"},
            {"id": "network", "name": "Red"},
            {"id": "peripheral", "name": "Periférico"},
            {"id": "other", "name": "Otro"}
        ]
    
    def get_statuses(self):
        """Obtiene los estados de activos disponibles."""
        return [
            {"id": "active", "name": "Activo"},
            {"id": "maintenance", "name": "Mantenimiento"},
            {"id": "retired", "name": "Retirado"},
            {"id": "storage", "name": "Almacenado"}
        ]
    
    def save(self):
        """Guarda o actualiza un activo en la base de datos."""
        if self.id:
            # Actualiza un activo existente
            query = """
                UPDATE assets 
                SET name = %s, type = %s, status = %s, purchase_date = %s, 
                    assigned_to = %s, updated_at = %s 
                WHERE id = %s
            """
            params = (self.name, self.type, self.status, self.purchase_date,
                     self.assigned_to, datetime.now(), self.id)
            self.db.execute_update(query, params)
            return self.id
        else:
            # Crea un nuevo activo
            query = """
                INSERT INTO assets (name, type, status, purchase_date, assigned_to, 
                                  created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (self.name, self.type, self.status, self.purchase_date,
                     self.assigned_to, self.created_at, self.updated_at)
            self.id = self.db.execute_update(query, params, return_id=True)
            return self.id
    
    @classmethod
    def find_by_status(cls, status):
        """Encuentra activos por su estado."""
        query = f"SELECT * FROM {cls.table_name} WHERE status = %s"
        return cls.db.execute_query(query, (status,))
    
    @classmethod
    def find_by_type(cls, type):
        """Encuentra activos por su tipo."""
        query = f"SELECT * FROM {cls.table_name} WHERE type = %s"
        return cls.db.execute_query(query, (type,))
    
    @classmethod
    def find_by_assigned_user(cls, user_id):
        """Encuentra activos asignados a un usuario específico."""
        query = f"SELECT * FROM {cls.table_name} WHERE assigned_to = %s"
        return cls.db.execute_query(query, (user_id,))
    
    @classmethod
    def get_asset_with_user_info(cls, asset_id):
        """Obtiene un activo con información del usuario asignado."""
        query = """
            SELECT a.*, u.name as assigned_user_name, u.email as assigned_user_email 
            FROM assets a
            LEFT JOIN users u ON a.assigned_to = u.id
            WHERE a.id = %s
        """
        result = cls.db.execute_query(query, (asset_id,))
        return result[0] if result else None
    
    @classmethod
    def get_all_with_user_info(cls):
        """Obtiene todos los activos con información de usuarios asignados."""
        query = """
            SELECT a.*, u.name as assigned_user_name, u.email as assigned_user_email 
            FROM assets a
            LEFT JOIN users u ON a.assigned_to = u.id
        """
        return cls.db.execute_query(query)