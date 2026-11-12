from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config.database import Database
from models.asset import BaseModel

class User(BaseModel):
    """Modelo para gestionar usuarios del sistema."""
    table_name = "users"
    
    def __init__(self, name, email, password=None, role="user", id=None, password_hash=None, area_id=None):
        self.id = id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        if password and not password_hash:
            self.set_password(password)
        self.role = role  # admin, manager, technician, user
        self.area_id = area_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def set_password(self, password):
        """Establece la contraseña encriptada."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica si la contraseña es correcta."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def save(self):
        """Guarda o actualiza un usuario en la base de datos."""
        if self.id:
            # Actualiza un usuario existente
            query = """
                UPDATE users 
                SET name = %s, email = %s, password_hash = %s, role = %s, area_id = %s, updated_at = %s
                WHERE id = %s
            """
            params = (self.name, self.email, self.password_hash, self.role, self.area_id,
                      datetime.now(), self.id)
            self.db.execute_update(query, params)
            return self.id
        else:
            # Crea un nuevo usuario
            query = """
                INSERT INTO users (name, email, password_hash, role, area_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (self.name, self.email, self.password_hash, self.role, self.area_id,
                      self.created_at, self.updated_at)
            self.id = self.db.execute_update(query, params, return_id=True)
            return self.id
    
    @classmethod
    def find_by_email(cls, email):
        """Encuentra un usuario por su correo electrónico."""
        query = f"SELECT * FROM {cls.table_name} WHERE LOWER(email) = LOWER(%s)"
        result = cls.db.execute_query(query, (email,))
        return result[0] if result else None
    
    @classmethod
    def find_by_role(cls, role):
        """Encuentra usuarios por su rol."""
        query = f"SELECT * FROM {cls.table_name} WHERE role = %s"
        return cls.db.execute_query(query, (role,))
    
    @classmethod
    def authenticate(cls, email, password):
        """Autentica un usuario mediante correo electrónico y contraseña."""
        user_data = cls.find_by_email(email)
        if not user_data or not user_data.get("is_active", True):
            return None
        
        user = cls(
            id=user_data['id'],
            name=user_data['name'],
            email=user_data['email'],
            role=user_data['role'],
            password_hash=user_data['password_hash']
        )
        
        if user.check_password(password):
            return user
        return None
    
    def is_admin(self):
        """Verifica si el usuario es administrador."""
        return self.role == "admin"
    
    def can_manage_assets(self):
        """Verifica si el usuario puede gestionar activos."""
        return self.role in ["admin", "manager"]
    
    def can_assign_tickets(self):
        """Verifica si el usuario puede asignar tickets."""
        return self.role in ["admin", "manager"]
