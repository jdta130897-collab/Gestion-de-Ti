from datetime import datetime
from config.database import Database
from models.asset import BaseModel

class Monitoring(BaseModel):
    """Modelo para gestionar datos de monitoreo."""
    table_name = "monitoring_data"
    
    def __init__(self, asset_id, metric_name, metric_value, timestamp=None, id=None):
        self.id = id
        self.asset_id = asset_id
        self.metric_name = metric_name
        self.metric_value = metric_value
        self.timestamp = timestamp or datetime.now()
    
    def save(self):
        """Guarda un registro de monitoreo en la base de datos."""
        if self.id:
            # Actualiza un registro existente
            query = """
                UPDATE monitoring_data 
                SET asset_id = %s, metric_name = %s, metric_value = %s, timestamp = %s
                WHERE id = %s
            """
            params = (self.asset_id, self.metric_name, self.metric_value, 
                      self.timestamp, self.id)
            self.db.execute_update(query, params)
            return self.id
        else:
            # Crea un nuevo registro
            query = """
                INSERT INTO monitoring_data (asset_id, metric_name, metric_value, timestamp) 
                VALUES (%s, %s, %s, %s)
            """
            params = (self.asset_id, self.metric_name, self.metric_value, self.timestamp)
            self.id = self.db.execute_update(query, params, return_id=True)
            return self.id
    
    @classmethod
    def find_by_asset(cls, asset_id):
        """Encuentra registros de monitoreo para un activo específico."""
        query = f"SELECT * FROM {cls.table_name} WHERE asset_id = %s ORDER BY timestamp DESC"
        return cls.db.execute_query(query, (asset_id,))
    
    @classmethod
    def find_by_metric(cls, metric_name):
        """Encuentra registros de monitoreo para una métrica específica."""
        query = f"SELECT * FROM {cls.table_name} WHERE metric_name = %s ORDER BY timestamp DESC"
        return cls.db.execute_query(query, (metric_name,))
    
    @classmethod
    def find_recent_by_asset(cls, asset_id, limit=100):
        """Encuentra los registros más recientes para un activo específico."""
        query = f"""
            SELECT * FROM {cls.table_name} 
            WHERE asset_id = %s 
            ORDER BY timestamp DESC
            LIMIT %s
        """
        return cls.db.execute_query(query, (asset_id, limit))
    
    @classmethod
    def get_asset_metrics(cls, asset_id, metric_name, hours=24):
        """Obtiene métricas de un activo para un período de tiempo específico."""
        query = f"""
            SELECT * FROM {cls.table_name} 
            WHERE asset_id = %s AND metric_name = %s AND timestamp >= NOW() - INTERVAL %s HOUR
            ORDER BY timestamp
        """
        return cls.db.execute_query(query, (asset_id, metric_name, hours))
    
    @classmethod
    def get_latest_metrics(cls, limit=10):
        """Obtiene las métricas más recientes con información del activo."""
        query = """
            SELECT m.*, a.name as asset_name, a.type as asset_type
            FROM monitoring_data m
            JOIN assets a ON m.asset_id = a.id
            ORDER BY m.timestamp DESC
            LIMIT %s
        """
        return cls.db.execute_query(query, (limit,))
    
    @classmethod
    def get_average_by_metric(cls, metric_name, hours=24):
        """Obtiene el promedio de una métrica para un período de tiempo específico."""
        query = """
            SELECT asset_id, AVG(metric_value) as average
            FROM monitoring_data
            WHERE metric_name = %s AND timestamp >= NOW() - INTERVAL %s HOUR
            GROUP BY asset_id
        """
        return cls.db.execute_query(query, (metric_name, hours))