import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import (
    MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, 
    MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
)

class EmailService:
    """Servicio para envío de emails."""
    
    def __init__(self):
        import os
        self.server = os.getenv("MAIL_SERVER", MAIL_SERVER)
        self.port = int(os.getenv("MAIL_PORT", MAIL_PORT))
        self.use_tls = MAIL_USE_TLS
        self.username = os.getenv("MAIL_USERNAME", MAIL_USERNAME)
        self.password = os.getenv("MAIL_PASSWORD", MAIL_PASSWORD)
        self.default_sender = os.getenv("MAIL_DEFAULT_SENDER", MAIL_DEFAULT_SENDER)
    
    def send_email(self, to_email, subject, html_content, from_email=None):
        """
        Envía un email.
        
        Args:
            to_email: Destinatario
            subject: Asunto
            html_content: Contenido HTML
            from_email: Remitente (opcional)
            
        Returns:
            Boolean indicando si se envió correctamente
        """
        # Verificar configuración de email
        if not self.server or not self.username or not self.password:
            return False  # El correo requiere credenciales SMTP reales.

        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email or self.default_sender
            msg['To'] = to_email
            
            # Añadir contenido HTML
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Conectar al servidor y enviar
            with smtplib.SMTP(self.server, self.port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.sendmail(msg['From'], msg['To'], msg.as_string())
            
            return True
        except Exception as e:
            print(f"Error al enviar email: {str(e)}")
            return False
    
    def send_welcome_email(self, email, name):
        """Envía email de bienvenida a un nuevo usuario."""
        subject = "Bienvenido al Sistema de Gestión TI"
        html_content = f"""
        <html>
        <head></head>
        <body>
            <h2>¡Bienvenido al Sistema de Gestión TI!</h2>
            <p>Hola {name},</p>
            <p>Tu cuenta ha sido creada exitosamente. Ahora puedes acceder a todas las funcionalidades de nuestro sistema.</p>
            <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
            <p>Saludos,<br>El equipo de Soporte TI</p>
        </body>
        </html>
        """
        return self.send_email(email, subject, html_content)
    
    def send_password_reset_email(self, email, name, reset_token):
        """Envía email para restablecer contraseña."""
        subject = "Restablecimiento de contraseña - Sistema de Gestión TI"
        html_content = f"""
        <html>
        <head></head>
        <body>
            <h2>Restablecimiento de contraseña</h2>
            <p>Hola {name},</p>
            <p>Has solicitado restablecer tu contraseña. Utiliza el siguiente código para completar el proceso:</p>
            <h3 style="background-color: #f0f0f0; padding: 10px; text-align: center;">{reset_token}</h3>
            <p>Si no solicitaste este cambio, puedes ignorar este mensaje.</p>
            <p>Saludos,<br>El equipo de Soporte TI</p>
        </body>
        </html>
        """
        return self.send_email(email, subject, html_content)
    
    def send_ticket_notification(self, email, name, ticket_id, ticket_title, ticket_status):
        """Envía notificación sobre un ticket."""
        status_map = {
            'open': 'Abierto',
            'in_progress': 'En progreso',
            'resolved': 'Resuelto',
            'closed': 'Cerrado'
        }
        status_display = status_map.get(ticket_status, ticket_status)
        
        subject = f"Actualización de ticket #{ticket_id} - {ticket_title}"
        html_content = f"""
        <html>
        <head></head>
        <body>
            <h2>Actualización de ticket #{ticket_id}</h2>
            <p>Hola {name},</p>
            <p>El estado del reporte "{ticket_title}" ha sido actualizado a <strong>{status_display}</strong>.</p>
            <p>Puedes ver más detalles accediendo al sistema.</p>
            <p>Saludos,<br>El equipo de Soporte TI</p>
        </body>
        </html>
        """
        return self.send_email(email, subject, html_content)
    
    def send_monitoring_alert(self, email, name, asset_name, metric_name, metric_value, threshold):
        """Envía alerta de monitoreo."""
        subject = f"ALERTA: {asset_name} - {metric_name} excede umbral"
        html_content = f"""
        <html>
        <head></head>
        <body>
            <h2 style="color: #cc0000;">ALERTA DE MONITOREO</h2>
            <p>Hola {name},</p>
            <p>Se ha detectado que el activo <strong>{asset_name}</strong> presenta valores anómalos:</p>
            <ul>
                <li><strong>{metric_name}:</strong> {metric_value} (Umbral: {threshold})</li>
            </ul>
            <p>Te recomendamos revisar este activo lo antes posible.</p>
            <p>Saludos,<br>El equipo de Soporte TI</p>
        </body>
        </html>
        """
        return self.send_email(email, subject, html_content)