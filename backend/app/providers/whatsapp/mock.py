"""
MockWhatsAppProvider — n'envoie AUCUN vrai message WhatsApp (un vrai envoi
nécessite un compte WhatsApp Business API réel, payant, à connecter plus
tard). Enregistre le message dans une table consultable (WhatsAppLog, page
"WhatsApp" du dashboard) comme preuve que l'envoi a bien été déclenché avec
le bon contenu — même principe que MockMessagingProvider pour les SMS.
"""
from sqlalchemy.orm import Session

from app.providers.whatsapp.base import WhatsAppProvider
from app.models.whatsapp_log import WhatsAppLog


class MockWhatsAppProvider(WhatsAppProvider):
    def __init__(self, db: Session, organization_id):
        self._db = db
        self._organization_id = organization_id

    def send_message(self, to_number: str, body: str) -> None:
        self._db.add(WhatsAppLog(organization_id=self._organization_id, to_number=to_number, body=body, provider="mock"))
        self._db.commit()
