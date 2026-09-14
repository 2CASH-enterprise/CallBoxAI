"""
Demandes d'exercice de droits RGPD (section 42/43 du cahier des charges) —
droit d'accès et droit à l'effacement, applicables à TOUTE la plateforme
(pas seulement la prospection), quel que soit l'agent à l'origine du
contact (accueil, service client, prospection...). Conservé même après
traitement, comme preuve que la demande a bien été honorée.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey

from app.core.database import Base
from app.models.distributor import GUID


class DataSubjectRequest(Base):
    __tablename__ = "data_subject_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=False)

    request_type = Column(String, nullable=False)  # "access" | "erasure"
    status = Column(String, default="pending")  # "pending" | "fulfilled"
    notes = Column(String, nullable=True)

    requested_at = Column(DateTime, default=datetime.utcnow)
    fulfilled_at = Column(DateTime, nullable=True)
