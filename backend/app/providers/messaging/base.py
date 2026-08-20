"""
Interface abstraite MessagingProvider (section 5 du cahier des charges) —
envoi de SMS. Aucune logique métier ne doit dépendre directement d'un
fournisseur particulier (Twilio, Vonage...) : elle ne doit connaître que
cette interface.
"""
from abc import ABC, abstractmethod


class MessagingProvider(ABC):
    @abstractmethod
    def send_sms(self, to_number: str, body: str) -> None:
        """Envoie un SMS. Doit lever une exception si l'envoi échoue."""
        ...
