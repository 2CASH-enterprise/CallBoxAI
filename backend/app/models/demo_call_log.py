"""
Journal des appels de démo déclenchés depuis la landing page publique
(section 1 — vitrine commerciale). Sert uniquement à limiter les abus (un
numéro ne peut déclencher qu'un nombre limité d'appels par jour) — pas de
organization_id ici, ce n'est pas une donnée client, c'est une donnée de la
plateforme elle-même.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime

from app.core.database import Base
from app.models.distributor import GUID


class DemoCallLog(Base):
    __tablename__ = "demo_call_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
