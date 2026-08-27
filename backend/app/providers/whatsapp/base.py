"""
Interface abstraite WhatsAppProvider (section 42 du cahier des charges —
prospection commerciale B2C/B2B). Aucune logique métier ne doit dépendre
directement d'un fournisseur particulier (Twilio WhatsApp Business API,
Meta Cloud API...) : elle ne doit connaître que cette interface.
"""
from abc import ABC, abstractmethod


class WhatsAppProvider(ABC):
    @abstractmethod
    def send_message(self, to_number: str, body: str) -> None:
        """Envoie un message WhatsApp. Doit lever une exception si l'envoi échoue."""
        ...
