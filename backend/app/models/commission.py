"""
Commission distributeur (section 39.5 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Float

from app.core.database import Base
from app.models.distributor import GUID


class Commission(Base):
    __tablename__ = "commissions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    distributor_id = Column(GUID(), ForeignKey("distributors.id"), nullable=False)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    period = Column(String, nullable=False)  # ex. "2026-08"
    base_amount = Column(Float, nullable=False)
    rate_applied = Column(Float, nullable=False)
    commission_amount = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending | validated | paid

    created_at = Column(DateTime, default=datetime.utcnow)
