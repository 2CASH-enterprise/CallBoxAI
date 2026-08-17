"""
Interface abstraite MessagingProvider (section 17 du cahier des charges).
"""
from abc import ABC, abstractmethod


class MessagingProvider(ABC):
    @abstractmethod
    def send_whatsapp(self, to_number: str, message: str, link: str | None = None) -> dict:
        ...

    @abstractmethod
    def send_sms(self, to_number: str, message: str) -> dict:
        ...


class MockMessagingProvider(MessagingProvider):
    """Simule l'envoi WhatsApp/SMS sans compte fournisseur réel."""

    def send_whatsapp(self, to_number: str, message: str, link: str | None = None) -> dict:
        return {"to": to_number, "channel": "whatsapp", "status": "sent", "message": message, "link": link}

    def send_sms(self, to_number: str, message: str) -> dict:
        return {"to": to_number, "channel": "sms", "status": "sent", "message": message}
