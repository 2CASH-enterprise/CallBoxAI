"""
Contact CRM (section 18 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey

from app.core.database import Base
from app.models.distributor import GUID


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=False)
    status = Column(String, default="Nouveau")

    created_at = Column(DateTime, default=datetime.utcnow)
