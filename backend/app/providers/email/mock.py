"""
MockEmailProvider — envoie de VRAIS emails SMTP, mais vers Mailhog (capteur
d'email de test déjà présent dans docker-compose.yml, section 40.3) plutôt
que vers de vraies boîtes mail. Consultable sur http://<serveur>:8025,
sans compte ni coût. À remplacer par un vrai fournisseur (SendGrid,
SMTP du client...) une fois en production réelle, sans changer le reste
du pipeline (section 5 et 16).
"""
import smtplib
from email.message import EmailMessage

from app.providers.email.base import EmailProvider


class MockEmailProvider(EmailProvider):
    def __init__(self, host: str = "mailhog", port: int = 1025, from_email: str = "reservations@callboxai.local"):
        self._host = host
        self._port = port
        self._from_email = from_email

    def send(self, to_email: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(self._host, self._port, timeout=5) as smtp:
            smtp.send_message(message)
