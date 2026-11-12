import os
from models.asset import Asset
from utils.validators import validate_asset
from datetime import datetime


class AssetController:
    """Controlador para gestionar activos de TI."""

    _sample_assets = [
        {
            "id": 1,
            "name": "Servidor Principal",
            "type": "hardware",
            "status": "active",
            "purchase_date": datetime.now()
            .date()
            .replace(year=datetime.now().year - 1),
            "assigned_to": 1,
            "assigned_to_name": "Admin User",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
        {
            "id": 2,
            "name": "Licencia Office 365",
            "type": "software",
            "status": "active",
            "purchase_date": datetime.now().date().replace(month=1),
            "assigned_to": None,
            "assigned_to_name": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
        {
            "id": 3,
            "name": "Switch de Red",
            "type": "network",
            "status": "maintenance",
            "purchase_date": datetime.now()
            .date()
            .replace(year=datetime.now().year - 2),
            "assigned_to": None,
            "assigned_to_name": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
        {
            "id": 4,
            "name": "Impresora Central",
            "type": "peripheral",
            "status": "active",
            "purchase_date": datetime.now().date().replace(month=6),
            "assigned_to": None,
            "assigned_to_name": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
        {
            "id": 5,
            "name": "UPS Backup",
            "type": "hardware",
            "status": "storage",
            "purchase_date": datetime.now()
            .date()
            .replace(year=datetime.now().year - 3),
            "assigned_to": None,
            "assigned_to_name": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
    ]

    @staticmethod
    def get_all_assets():
        """Obtiene todos los activos."""
        # Verificar si debemos usar datos de ejemplo

        # Usar la base de datos
        try:
            asset_model = Asset()
            return asset_model.get_all()
        except Exception as e:
            print(f"Error en get_all_assets: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_asset(asset_id):
        """Obtiene un activo por su ID."""
        # Verificar si debemos usar datos de ejemplo

        # Usar la base de datos
        try:
            asset_model = Asset()
            return asset_model.get_by_id(asset_id)
        except Exception as e:
            print(f"Error en get_asset: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def create_asset(asset_data):
        """Crea un nuevo activo."""
        # Verificar si debemos usar datos de ejemplo

        # Usar la base de datos
        try:
            asset_model = Asset()
            return asset_model.create(asset_data)
        except Exception as e:
            print(f"Error en create_asset: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def update_asset(asset_id, asset_data):
        """Actualiza un activo existente."""
        # Verificar si debemos usar datos de ejemplo

        # Usar la base de datos
        try:
            asset_model = Asset()
            return asset_model.update(asset_id, asset_data)
        except Exception as e:
            print(f"Error en update_asset: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def delete_asset(asset_id):
        """Elimina un activo."""
        # Verificar si debemos usar datos de ejemplo

        # Usar la base de datos
        try:
            asset_model = Asset()
            return asset_model.delete(asset_id)
        except Exception as e:
            print(f"Error en delete_asset: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_asset_types():
        """Obtiene los tipos de activos disponibles."""
        # Esta información es estática y no requiere base de datos
        return [
            {"id": "hardware", "name": "Hardware"},
            {"id": "software", "name": "Software"},
            {"id": "network", "name": "Red"},
            {"id": "peripheral", "name": "Periférico"},
            {"id": "other", "name": "Otro"},
        ]

    @staticmethod
    def get_asset_statuses():
        """Obtiene los estados de activos disponibles."""
        # Esta información es estática y no requiere base de datos
        return [
            {"id": "active", "name": "Activo"},
            {"id": "maintenance", "name": "Mantenimiento"},
            {"id": "retired", "name": "Retirado"},
            {"id": "storage", "name": "Almacenado"},
        ]

    @staticmethod
    def get_users_for_assignment():
        """Obtiene la lista de usuarios para asignación."""
        # Para datos de ejemplo, solo retornamos el admin

        # En una implementación real, esto buscaría en la tabla de usuarios
        try:
            from models.user import User

            return {"status": "success", "data": User.find_all()}
        except Exception as e:
            print(f"Error en get_users_for_assignment: {e}")
            return {"status": "error", "message": str(e)}
