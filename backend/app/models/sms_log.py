"""
Journal des SMS envoyés (section 5/16 du cahier des charges).
En mode Mock, aucun SMS n'est réellement délivré (contrairement à l'email
via Mailhog, il n'existe pas d'équivalent gratuit pour le SMS) — cette table
sert de preuve consultable que l'envoi a bien été déclenché avec le bon
contenu, à la place d'une vraie livraison.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text

from app.core.database import Base
from app.models.distributor import GUID


class SmsLog(Base):
    __tablename__ = "sms_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    to_number = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    provider = Column(String, default="mock")  # mock | twilio

    created_at = Column(DateTime, default=datetime.utcnow)
