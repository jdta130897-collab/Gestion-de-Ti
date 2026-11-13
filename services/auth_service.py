import secrets
import string
import jwt
import datetime
from config.settings import SECRET_KEY, API_KEY_EXPIRY_DAYS
from config.database import Database
from models.user import User
from utils.timezone import utc_now

class AuthService:
    """Servicio para autenticación y autorización."""
    
    def __init__(self):
        self.db = Database()
    
    def generate_api_key(self, user_id):
        """
        Genera una API key para un usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            API key generada
        """
        # Verificar si el usuario existe
        user = User.find_by_id(user_id)
        if not user:
            raise ValueError("Usuario no encontrado")
        
        # Generar token aleatorio
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # Fecha de expiración en UTC
        now = utc_now()
        expiry_date = now + datetime.timedelta(days=API_KEY_EXPIRY_DAYS)
        
        # Almacenar en la base de datos (crear tabla si no existe)
        self._create_api_keys_table_if_not_exists()
        
        # Verificar si ya existe una API key para este usuario
        query = "SELECT id FROM api_keys WHERE user_id = %s"
        result = self.db.execute_query(query, (user_id,))
        
        if result:
            # Actualizar API key existente
            query = """
                UPDATE api_keys 
                SET api_key = %s, expiry_date = %s, updated_at = %s
                WHERE user_id = %s
            """
            params = (api_key, expiry_date, now, user_id)
        else:
            # Crear nueva API key
            query = """
                INSERT INTO api_keys (user_id, api_key, expiry_date, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            params = (user_id, api_key, expiry_date, now, now)
        
        self.db.execute_update(query, params)
        
        return api_key
    
    def validate_api_key(self, api_key):
        """
        Valida una API key.
        
        Args:
            api_key: API key a validar
            
        Returns:
            Boolean indicando si la API key es válida
        """
        self._create_api_keys_table_if_not_exists()
        
        query = """
            SELECT * FROM api_keys 
            WHERE api_key = %s AND expiry_date > %s
        """
        result = self.db.execute_query(query, (api_key, utc_now()))
        
        return bool(result)
    
    def get_user_from_api_key(self, api_key):
        """
        Obtiene el usuario asociado a una API key.
        
        Args:
            api_key: API key
            
        Returns:
            ID del usuario o None si la API key no es válida
        """
        self._create_api_keys_table_if_not_exists()
        
        query = """
            SELECT user_id FROM api_keys 
            WHERE api_key = %s AND expiry_date > %s
        """
        result = self.db.execute_query(query, (api_key, utc_now()))
        
        if result:
            return result[0]['user_id']
        return None
    
    def revoke_api_key(self, user_id):
        """
        Revoca la API key de un usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Boolean indicando si se revocó correctamente
        """
        self._create_api_keys_table_if_not_exists()
        
        query = "DELETE FROM api_keys WHERE user_id = %s"
        affected_rows = self.db.execute_update(query, (user_id,))
        
        return affected_rows > 0
    
    def generate_jwt_token(self, user_data, expires_in=86400):
        """
        Genera un token JWT para un usuario.
        
        Args:
            user_data: Datos del usuario
            expires_in: Tiempo de expiración en segundos (default: 24 horas)
            
        Returns:
            Token JWT generado
        """
        # Configurar carga útil del token
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            'sub': user_data['id'],
            'name': user_data['name'],
            'email': user_data['email'],
            'role': user_data['role'],
            'iat': now_utc,
            'exp': now_utc + datetime.timedelta(seconds=expires_in)
        }
        
        # Generar token JWT
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        
        return token
    
    def validate_jwt_token(self, token):
        """
        Valida un token JWT.
        
        Args:
            token: Token JWT a validar
            
        Returns:
            Datos del usuario si el token es válido, None en caso contrario
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def _create_api_keys_table_if_not_exists(self):
        """Crea la tabla de API keys si no existe."""
        if self.db.is_postgres:
            # En Supabase el esquema se prepara mediante migraciones, no en cada petición.
            return
        query = """
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
        self.db.execute_update(query)
