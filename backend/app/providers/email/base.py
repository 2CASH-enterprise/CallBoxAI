"""
Interface abstraite EmailProvider (section 5 du cahier des charges).
Aucune logique métier ne doit dépendre directement d'un fournisseur d'email
particulier (SMTP direct, SendGrid, Mailgun, AWS SES...) : elle ne doit
connaître que cette interface.
"""
from abc import ABC, abstractmethod


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to_email: str, subject: str, body: str) -> None:
        """Envoie un email. Doit lever une exception si l'envoi échoue."""
        ...
