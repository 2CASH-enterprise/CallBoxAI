"""
Organization = une entreprise cliente (tenant). Section 3 du cahier des charges :
toutes les données métier sont rattachées à un organization_id, et jamais
accessibles à une autre organization.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey

from app.core.database import Base
from app.models.distributor import GUID


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)

    # Rattachement optionnel à un distributeur (section 39.2)
    distributor_id = Column(GUID(), ForeignKey("distributors.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
