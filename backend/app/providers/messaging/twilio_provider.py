"""
TwilioMessagingProvider — implémentation RÉELLE de MessagingProvider
(section 16 du cahier des charges), utilisant le SDK officiel Twilio.

N'est instanciée et utilisée que si MESSAGING_PROVIDER=twilio ET que les
identifiants Twilio sont renseignés (voir app.core.providers). Tant que ce
n'est pas le cas, aucun SMS réel — donc aucun coût — n'est jamais déclenché.
Coût réel une fois activé : environ 0,01 à 0,08 $ par SMS selon le pays de
destination (tarification Twilio).
"""
from twilio.rest import Client

from app.providers.messaging.base import MessagingProvider


class TwilioMessagingProvider(MessagingProvider):
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self._client = Client(account_sid, auth_token)
        self._from_number = from_number

    def send_sms(self, to_number: str, body: str) -> None:
        self._client.messages.create(to=to_number, from_=self._from_number, body=body)
