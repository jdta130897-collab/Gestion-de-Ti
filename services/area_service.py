from config.database import Database


class AreaService:
    @staticmethod
    def all(active_only=False):
        where = 'WHERE a.is_active=TRUE' if active_only else ''
        return Database().execute_query(f'''SELECT a.*, (SELECT COUNT(*) FROM users u WHERE u.area_id=a.id) AS members
            FROM areas a {where} ORDER BY a.code='TI' DESC, a.name''')

    @staticmethod
    def get(area_id):
        rows = Database().execute_query('SELECT * FROM areas WHERE id=%s', (area_id,))
        return rows[0] if rows else None

    @staticmethod
    def ti_id():
        return Database().execute_query("SELECT id FROM areas WHERE code='TI'")[0]['id']

    @staticmethod
    def save(name, code, area_id=None):
        name, code = name.strip(), code.strip().upper()
        import re
        if not 3 <= len(name) <= 100 or not re.fullmatch(r'[A-Z0-9_-]{2,20}', code):
            raise ValueError('Ingresa un nombre de 3 a 100 caracteres y un código de 2 a 20 letras, números o guiones.')
        db = Database()
        existing = AreaService.get(area_id) if area_id else None
        if existing and existing['code'] == 'TI' and code != 'TI':
            raise ValueError('El código TI está reservado para el área que atiende las solicitudes.')
        duplicates = db.execute_query('SELECT id FROM areas WHERE (code=%s OR name=%s) AND id<>%s', (code, name, area_id or 0))
        if duplicates:
            raise ValueError('Ya existe un área con ese nombre o código.')
        if area_id:
            if not existing:
                raise ValueError('Área no encontrada.')
            db.execute_update('UPDATE areas SET name=%s, code=%s WHERE id=%s', (name, code, area_id))
            return area_id
        return db.execute_update('INSERT INTO areas (name,code) VALUES (%s,%s)', (name, code), return_id=True)

    @staticmethod
    def validate_membership(role, area_id, user_id=None):
        if role not in ('super_admin', 'admin', 'manager', 'technician', 'user'):
            raise ValueError('Rol no válido.')
        area = AreaService.get(area_id) if area_id else None
        if not area or not area['is_active']:
            raise ValueError('Selecciona un área activa para el usuario.')
        if role == 'manager':
            existing = Database().execute_query("SELECT id FROM users WHERE area_id=%s AND role='manager' AND is_active=TRUE AND id<>%s", (area_id,user_id or 0))
            if existing:
                raise ValueError('Esta área ya tiene un encargado activo. Cambia primero el encargado anterior a trabajador.')
        if role in ('admin','technician'):
            raise ValueError('Selecciona Encargado de área o Trabajador; los roles anteriores ya no se asignan.')

    @staticmethod
    def user_scope(user_id):
        rows = Database().execute_query('''SELECT u.id,u.role,u.area_id,u.is_active,
            a.code AS area_code,a.name AS area_name,a.is_active AS area_active
            FROM users u LEFT JOIN areas a ON a.id=u.area_id WHERE u.id=%s''', (user_id,))
        return rows[0] if rows else None
