class TicketService:
    def create_ticket_from_text(self, texto: str) -> dict:
        # Lógica básica para crear un ticket a partir de texto
        # Aquí puedes usar NLP o reglas para extraer prioridad, usuario, etc.
        nuevo_ticket = {
            "titulo": texto[:60],
            "descripcion": texto,
            "prioridad": "Media"
        }
        # Acá iría lógica para guardar en BD
        return nuevo_ticket
