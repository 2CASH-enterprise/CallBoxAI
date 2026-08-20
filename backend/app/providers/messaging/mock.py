"""
MockMessagingProvider — n'envoie AUCUN vrai SMS (contrairement à l'email, il
n'existe pas d'équivalent gratuit de Mailhog pour le SMS : un vrai envoi
nécessite toujours un compte payant). Enregistre le SMS dans une table
consultable (SmsLog, page "SMS" du dashboard) comme preuve que l'envoi a
bien été déclenché avec le bon contenu (section 40.3).

À remplacer par TwilioMessagingProvider (déjà prêt, voir twilio_provider.py)
une fois un compte Twilio réellement configuré, sans changer le reste du
pipeline (section 5 et 16).
"""
from sqlalchemy.orm import Session

from app.providers.messaging.base import MessagingProvider
from app.models.sms_log import SmsLog


class MockMessagingProvider(MessagingProvider):
    def __init__(self, db: Session, organization_id):
        self._db = db
        self._organization_id = organization_id

    def send_sms(self, to_number: str, body: str) -> None:
        self._db.add(SmsLog(organization_id=self._organization_id, to_number=to_number, body=body, provider="mock"))
        self._db.commit()
