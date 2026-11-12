from models.user import User
from utils.validators import validate_user
from services.auth_service import AuthService
from services.email_service import EmailService

class UserController:
    """Controlador para gestionar usuarios del sistema."""
    
    @staticmethod
    def get_all_users():
        """Obtiene todos los usuarios."""
        try:
            # Obtener todos los usuarios pero sin devolver contraseñas
            users = User.find_all()
            for user in users:
                if 'password_hash' in user:
                    del user['password_hash']
            
            return {"status": "success", "data": users}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def get_user(user_id):
        """Obtiene un usuario específico."""
        try:
            user = User.find_by_id(user_id)
            if not user:
                return {"status": "error", "message": "Usuario no encontrado"}
            
            # No devolver contraseña
            if 'password_hash' in user:
                del user['password_hash']
            
            return {"status": "success", "data": user}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def create_user(user_data):
        """Crea un nuevo usuario."""
        try:
            from services.area_service import AreaService
            user_data = dict(user_data)
            user_data.setdefault('area_id', AreaService.ti_id())
            AreaService.validate_membership(user_data.get('role', 'user'), user_data['area_id'])
            # Validar datos del usuario
            validation = validate_user(user_data)
            if not validation["valid"]:
                return {"status": "error", "message": validation["errors"]}
            
            # Verificar si el email ya existe
            existing_user = User.find_by_email(user_data.get("email"))
            if existing_user:
                return {"status": "error", "message": "El correo electrónico ya está registrado"}
            
            # Crear nuevo usuario
            user = User(
                name=user_data.get("name"),
                email=user_data.get("email"),
                password=user_data.get("password"),
                role=user_data.get("role", "user"),
                area_id=user_data.get("area_id")
            )
            
            user_id = user.save()
            
            # Enviar email de bienvenida
            email_service = EmailService()
            email_service.send_welcome_email(user_data.get("email"), user_data.get("name"))
            
            return {
                "status": "success", 
                "message": "Usuario creado correctamente", 
                "id": user_id
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def update_user(user_id, user_data):
        """Actualiza un usuario existente."""
        try:
            # Verificar si el usuario existe
            existing_user = User.find_by_id(user_id)
            if not existing_user:
                return {"status": "error", "message": "Usuario no encontrado"}

            from services.area_service import AreaService
            AreaService.validate_membership(user_data.get('role', existing_user['role']), user_data.get('area_id', existing_user.get('area_id')), user_id)
            if existing_user['role'] == 'super_admin' and (user_data.get('role', 'super_admin') != 'super_admin' or not user_data.get('is_active', True)):
                if len(User.db.execute_query("SELECT id FROM users WHERE role='super_admin' AND is_active=TRUE")) <= 1:
                    return {'status': 'error', 'message': 'Debe existir al menos un superadministrador activo.'}
            
            # Validar datos del usuario
            validation = validate_user(user_data, update=True)
            if not validation["valid"]:
                return {"status": "error", "message": validation["errors"]}
            
            # Si se está actualizando el correo, verificar que no exista otro usuario con ese correo
            if "email" in user_data and user_data["email"] != existing_user["email"]:
                check_email = User.find_by_email(user_data["email"])
                if check_email and check_email["id"] != user_id:
                    return {"status": "error", "message": "El correo electrónico ya está en uso"}
            
            # Crear objeto usuario con datos existentes
            user = User(
                id=user_id,
                name=user_data.get("name", existing_user["name"]),
                email=user_data.get("email", existing_user["email"]),
                role=user_data.get("role", existing_user["role"]),
                password_hash=existing_user["password_hash"],
                area_id=user_data.get("area_id", existing_user.get("area_id"))
            )
            
            # Actualizar contraseña si se proporciona
            if "password" in user_data and user_data["password"]:
                user.set_password(user_data["password"])
            
            user.save()
            if "is_active" in user_data:
                user.db.execute_update("UPDATE users SET is_active = %s WHERE id = %s", (bool(user_data["is_active"]), user_id))
            return {"status": "success", "message": "Usuario actualizado correctamente"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def delete_user(user_id):
        """Elimina un usuario existente."""
        try:
            # Verificar si el usuario existe
            existing_user = User.find_by_id(user_id)
            if not existing_user:
                return {"status": "error", "message": "Usuario no encontrado"}

            if existing_user['role'] == 'super_admin':
                if len(User.db.execute_query("SELECT id FROM users WHERE role='super_admin' AND is_active=TRUE")) <= 1:
                    return {'status': 'error', 'message': 'No se puede eliminar al último superadministrador.'}
            
            # Eliminar usuario
            User.delete(user_id)
            return {"status": "success", "message": "Usuario eliminado correctamente"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def login(email, password):
        """Autentica un usuario y genera una sesión."""
        try:
            user = User.authenticate(email, password)
            if not user:
                return {"status": "error", "message": "Credenciales inválidas"}
            from services.area_service import AreaService
            scope = AreaService.user_scope(user.id)
            if not scope or (not scope['area_active'] and scope['role'] != 'super_admin'):
                return {'status': 'error', 'message': 'Tu área está inactiva. Contacta al superadministrador.'}
            
            # No devolver la contraseña
            user_data = {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role
            }
            
            return {"status": "success", "message": "Inicio de sesión exitoso", "user": user_data}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def generate_api_key(user_id):
        """Genera una API key para un usuario específico."""
        try:
            # Verificar si el usuario existe
            existing_user = User.find_by_id(user_id)
            if not existing_user:
                return {"status": "error", "message": "Usuario no encontrado"}
            
            # Generar API key
            auth_service = AuthService()
            api_key = auth_service.generate_api_key(user_id)
            
            return {"status": "success", "api_key": api_key}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def get_users_by_role(role):
        """Obtiene usuarios por rol."""
        try:
            users = User.find_by_role(role)
            # No devolver contraseñas
            for user in users:
                if 'password_hash' in user:
                    del user['password_hash']
            
            return {"status": "success", "data": users}
        except Exception as e:
            return {"status": "error", "message": str(e)}
