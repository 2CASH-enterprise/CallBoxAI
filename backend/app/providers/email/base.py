"""
Interface abstraite EmailProvider (section 5 du cahier des charges).
Aucune logique métier ne doit dépendre directement d'un fournisseur d'email
particulier (SMTP direct, SendGrid, Mailgun, AWS SES...) : elle ne doit
connaître que cette interface.
"""
from abc import ABC, abstractmethod


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
        """
        Envoie un email. `body` (texte brut) sert de version de secours pour
        les clients mail qui ne supportent pas le HTML ; `html_body` est
        utilisé si fourni pour une présentation soignée. Doit lever une
        exception si l'envoi échoue.
        """
        ...
