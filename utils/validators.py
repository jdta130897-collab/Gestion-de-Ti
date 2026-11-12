# -*- coding: utf-8 -*-
import re
from datetime import datetime

def validate_asset(data, update=False):
    """
    Valida datos de un activo.
    
    Args:
        data: Diccionario con datos del activo
        update: Indica si es una actualización (no todos los campos son obligatorios)
        
    Returns:
        Dict con resultado de validación
    """
    errors = []
    
    # Campos obligatorios para creación
    if not update:
        required_fields = ['name', 'type', 'status', 'purchase_date']
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"El campo '{field}' es obligatorio")
    
    # Validar nombre si está presente
    if 'name' in data and data['name']:
        if len(data['name']) < 3 or len(data['name']) > 100:
            errors.append("El nombre debe tener entre 3 y 100 caracteres")
    
    # Validar tipo si está presente
    if 'type' in data and data['type']:
        valid_types = ['hardware', 'software', 'network', 'peripheral', 'other']
        if data['type'].lower() not in valid_types:
            errors.append(f"El tipo debe ser uno de: {', '.join(valid_types)}")
    
    # Validar estado si está presente
    if 'status' in data and data['status']:
        valid_statuses = ['active', 'maintenance', 'retired', 'storage']
        if data['status'].lower() not in valid_statuses:
            errors.append(f"El estado debe ser uno de: {', '.join(valid_statuses)}")
    
    # Validar fecha de compra si está presente
    if 'purchase_date' in data and data['purchase_date']:
        try:
            if isinstance(data['purchase_date'], str):
                datetime.strptime(data['purchase_date'], '%Y-%m-%d')
            # Si ya es un objeto date o datetime, no necesita validación adicional
        except ValueError:
            errors.append("La fecha de compra debe tener formato YYYY-MM-DD")
    
    return {"valid": len(errors) == 0, "errors": errors}

def validate_ticket(data, update=False):
    """
    Valida datos de un ticket.
    
    Args:
        data: Diccionario con datos del ticket
        update: Indica si es una actualización (no todos los campos son obligatorios)
        
    Returns:
        Dict con resultado de validación
    """
    errors = []
    
    # Campos obligatorios para creación
    if not update:
        required_fields = ['title', 'description', 'priority', 'created_by']
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"El campo '{field}' es obligatorio")
    
    # Validar título si está presente
    if 'title' in data and data['title']:
        if len(data['title']) < 5 or len(data['title']) > 100:
            errors.append("El título debe tener entre 5 y 100 caracteres")
    
    # Validar descripción si está presente
    if 'description' in data and data['description']:
        if len(data['description']) < 10:
            errors.append("La descripción debe tener al menos 10 caracteres")
    
    # Validar prioridad si está presente
    if 'priority' in data and data['priority']:
        valid_priorities = ['low', 'medium', 'high', 'critical']
        if data['priority'].lower() not in valid_priorities:
            errors.append(f"La prioridad debe ser una de: {', '.join(valid_priorities)}")
    
    # Validar estado si está presente
    if 'status' in data and data['status']:
        valid_statuses = ['open', 'in_progress', 'resolved', 'closed']
        if data['status'].lower() not in valid_statuses:
            errors.append(f"El estado debe ser uno de: {', '.join(valid_statuses)}")
    
    return {"valid": len(errors) == 0, "errors": errors}

def validate_user(data, update=False):
    """
    Valida datos de un usuario.
    
    Args:
        data: Diccionario con datos del usuario
        update: Indica si es una actualización (no todos los campos son obligatorios)
        
    Returns:
        Dict con resultado de validación
    """
    errors = []
    
    # Campos obligatorios para creación
    if not update:
        required_fields = ['name', 'email', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"El campo '{field}' es obligatorio")
    
    # Validar nombre si está presente
    if 'name' in data and data['name']:
        if len(data['name']) < 3 or len(data['name']) > 100:
            errors.append("El nombre debe tener entre 3 y 100 caracteres")
    
    # Validar email si está presente
    if 'email' in data and data['email']:
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, data['email']):
            errors.append("El email no tiene un formato válido")
    
    # Validar contraseña si está presente
    if 'password' in data and data['password']:
        if len(data['password']) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres")
    
    # Validar rol si está presente
    if 'role' in data and data['role']:
        valid_roles = ['super_admin', 'admin', 'manager', 'technician', 'user']
        if data['role'].lower() not in valid_roles:
            errors.append(f"El rol debe ser uno de: {', '.join(valid_roles)}")
    
    return {"valid": len(errors) == 0, "errors": errors}
