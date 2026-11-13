from datetime import datetime
from config.database import Database
from models.asset import BaseModel
from utils.timezone import lima_day_bounds_to_utc, utc_now

class Ticket(BaseModel):
    """Modelo para gestionar tickets de soporte."""
    table_name = "tickets"

    def __init__(self, title, description, status, priority, created_by,
                 assigned_to=None, related_asset=None, id=None, resolved_at=None,
                 origin_area_id=None, destination_area_id=None, request_kind='incident',
                 channel='manual', attempt_id=None, evaluation_session_id=None):
        self.id = id
        self.title = title
        self.description = description
        self.status = status  # open, in_progress, resolved, closed
        self.priority = priority  # low, medium, high, critical
        self.created_by = created_by
        self.origin_area_id = origin_area_id
        self.destination_area_id = destination_area_id
        self.request_kind = request_kind
        self.channel = channel
        self.attempt_id = attempt_id
        self.evaluation_session_id = evaluation_session_id
        self.assigned_to = assigned_to
        self.related_asset = related_asset
        self.resolved_at = resolved_at
        now = utc_now()
        self.created_at = now
        self.updated_at = now

    def save(self, tx=None):
        """Guarda o actualiza un ticket en la base de datos."""
        exec_fn = tx.execute if tx is not None else self.db.execute_update
        if self.id:
            # Actualiza un ticket existente
            query = """
                UPDATE tickets
                SET title = %s, description = %s, status = %s, priority = %s, request_kind = %s,
                    assigned_to = %s, related_asset = %s, updated_at = %s, resolved_at = %s
                WHERE id = %s
            """
            params = (self.title, self.description, self.status, self.priority, self.request_kind,
                     self.assigned_to, self.related_asset, utc_now(),
                     self.resolved_at, self.id)
            exec_fn(query, params)
            return self.id
        else:
            # Crea un nuevo ticket
            query = """
                INSERT INTO tickets (title, description, status, priority, created_by,
                                    assigned_to, related_asset, created_at, updated_at,
                                    origin_area_id, destination_area_id, request_kind, channel,
                                    attempt_id, evaluation_session_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (self.title, self.description, self.status, self.priority,
                     self.created_by, self.assigned_to, self.related_asset,
                     self.created_at, self.updated_at, self.origin_area_id, self.destination_area_id,
                     self.request_kind, self.channel, self.attempt_id, self.evaluation_session_id)
            self.id = exec_fn(query, params, return_id=True)
            return self.id

    @classmethod
    def get_by_id(cls, ticket_id):
        """Obtiene un ticket por su ID."""
        query = """
            SELECT id, title, description, status, priority, created_by,
                   assigned_to, related_asset, created_at, updated_at, resolved_at, origin_area_id, destination_area_id, request_kind
            FROM tickets
            WHERE id = %s
        """
        params = (ticket_id,)
        result = cls.db.execute_query(query, params)
        if result:
            ticket_data = result[0]
            ticket = cls(
                id=ticket_data["id"],
                title=ticket_data["title"],
                description=ticket_data["description"],
                status=ticket_data["status"],
                priority=ticket_data["priority"],
                created_by=ticket_data["created_by"],
                assigned_to=ticket_data["assigned_to"],
                related_asset=ticket_data["related_asset"],
                resolved_at=ticket_data["resolved_at"],
                origin_area_id=ticket_data["origin_area_id"], destination_area_id=ticket_data["destination_area_id"], request_kind=ticket_data["request_kind"],
            )
            ticket.created_at = ticket_data["created_at"]
            ticket.updated_at = ticket_data["updated_at"]
            return ticket
        return None

    @classmethod
    def find_by_status(cls, status):
        """Encuentra tickets por su estado."""
        query = f"SELECT * FROM {cls.table_name} WHERE status = %s"
        return cls.db.execute_query(query, (status,))

    @classmethod
    def find_by_priority(cls, priority):
        """Encuentra tickets por su prioridad."""
        query = f"SELECT * FROM {cls.table_name} WHERE priority = %s"
        return cls.db.execute_query(query, (priority,))

    @classmethod
    def find_by_assigned_user(cls, user_id):
        """Encuentra tickets asignados a un usuario específico."""
        query = f"SELECT * FROM {cls.table_name} WHERE assigned_to = %s"
        return cls.db.execute_query(query, (user_id,))

    @classmethod
    def find_by_created_user(cls, user_id):
        """Encuentra tickets creados por un usuario específico."""
        query = f"SELECT * FROM {cls.table_name} WHERE created_by = %s"
        return cls.db.execute_query(query, (user_id,))

    @classmethod
    def get_ticket_with_details(cls, ticket_id):
        """Obtiene un ticket con detalles completos de usuarios y activos."""
        query = """
            SELECT t.*,
                   c.name as created_by_name, c.email as created_by_email,
                   a.name as assigned_to_name, a.email as assigned_to_email,
                   ass.name as asset_name, ass.type as asset_type,
                   origin.name as origin_area_name, destination.name as destination_area_name
            FROM tickets t
            JOIN users c ON t.created_by = c.id
            LEFT JOIN users a ON t.assigned_to = a.id
            LEFT JOIN assets ass ON t.related_asset = ass.id
            LEFT JOIN areas origin ON origin.id=t.origin_area_id
            LEFT JOIN areas destination ON destination.id=t.destination_area_id
            WHERE t.id = %s
        """
        result = cls.db.execute_query(query, (ticket_id,))
        return result[0] if result else None

    @classmethod
    def get_all_with_details(cls, date_filter=None, priority_filter=None):
        """Obtiene todos los tickets con detalles completos, aplicando filtros opcionales."""
        query = """
            SELECT t.*,
                   c.name as created_by_name,
                   a.name as assigned_to_name,
                   ass.name as asset_name,
                   origin.name as origin_area_name, destination.name as destination_area_name
            FROM tickets t
            JOIN users c ON t.created_by = c.id
            LEFT JOIN users a ON t.assigned_to = a.id
            LEFT JOIN assets ass ON t.related_asset = ass.id
            LEFT JOIN areas origin ON origin.id=t.origin_area_id
            LEFT JOIN areas destination ON destination.id=t.destination_area_id
        """
        conditions = []
        params = []

        # Filtro por fecha calendario en Lima (UTC-5) convertido a rango UTC
        if date_filter:
            try:
                parsed_date = datetime.strptime(str(date_filter), "%Y-%m-%d")
                utc_start, utc_end = lima_day_bounds_to_utc(parsed_date, parsed_date)
                conditions.append("t.created_at >= %s AND t.created_at < %s")
                params.extend([utc_start, utc_end])
            except ValueError:
                conditions.append("DATE(t.created_at) = %s")
                params.append(date_filter)

        # Filtro por prioridad
        if priority_filter:
            conditions.append("t.priority = %s")
            params.append(priority_filter)

        # Añadir condiciones al query si existen
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # Ordenamiento
        query += """
            ORDER BY
                CASE t.status
                    WHEN 'open' THEN 1
                    WHEN 'in_progress' THEN 2
                    WHEN 'resolved' THEN 3
                    WHEN 'closed' THEN 4
                END,
                CASE t.priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                t.created_at DESC
        """

        return cls.db.execute_query(query, params)

    def add_comment(self, user_id, comment_text, tx=None):
        """Añade un comentario a un ticket."""
        if not self.id:
            raise ValueError("El ticket debe guardarse primero antes de añadir comentarios")

        query = """
            INSERT INTO ticket_comments (ticket_id, user_id, comment, created_at)
            VALUES (%s, %s, %s, %s)
        """
        params = (self.id, user_id, comment_text, utc_now())
        if tx is not None:
            tx.execute(query, params)
        else:
            self.db.execute_update(query, params)

    @classmethod
    def get_comments(cls, ticket_id):
        """Obtiene los comentarios de un ticket."""
        query = """
            SELECT tc.*, u.name as user_name, u.email as user_email
            FROM ticket_comments tc
            JOIN users u ON tc.user_id = u.id
            WHERE tc.ticket_id = %s
            ORDER BY tc.created_at
        """
        return cls.db.execute_query(query, (ticket_id,))

    def delete(self):
        """Elimina un ticket y sus comentarios asociados."""
        if not self.id:
            raise ValueError("El ticket debe tener un ID para ser eliminado")

        # Eliminar comentarios asociados
        query = "DELETE FROM ticket_comments WHERE ticket_id = %s"
        params = (self.id,)
        self.db.execute_update(query, params)

        # Eliminar el ticket
        query = f"DELETE FROM {self.table_name} WHERE id = %s"
        params = (self.id,)
        self.db.execute_update(query, params)
