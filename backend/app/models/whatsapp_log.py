"""
Journal des messages WhatsApp envoyés (section 42 du cahier des charges —
prospection commerciale). En mode Mock, aucun message n'est réellement
délivré (compte WhatsApp Business API réel à connecter plus tard) — cette
table sert de preuve consultable que l'envoi a bien été déclenché avec le
bon contenu, même principe que SmsLog.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text

from app.core.database import Base
from app.models.distributor import GUID


class WhatsAppLog(Base):
    __tablename__ = "whatsapp_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=True)  # section 42 : nécessaire au résumé combiné d'équipe

    to_number = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    provider = Column(String, default="mock")  # mock | twilio_whatsapp | meta_cloud

    created_at = Column(DateTime, default=datetime.utcnow)
