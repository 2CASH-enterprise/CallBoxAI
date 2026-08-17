"""
Dossier KYC (section 41 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text

from app.core.database import Base
from app.models.distributor import GUID


class KYCDossier(Base):
    __tablename__ = "kyc_dossiers"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=False)

    status = Column(String, default="not_started")
    link_token = Column(String, nullable=True, unique=True)
    link_expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)


class KYCDocument(Base):
    __tablename__ = "kyc_documents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    kyc_dossier_id = Column(GUID(), ForeignKey("kyc_dossiers.id"), nullable=False)

    type = Column(String, nullable=False)  # id_card | proof_of_address | selfie | signature
    file_url = Column(Text, nullable=True)
    verification_status = Column(String, default="pending")

    uploaded_at = Column(DateTime, default=datetime.utcnow)
