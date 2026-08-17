"""
Rattachement d'un utilisateur à une organisation, avec un rôle
(section 6.1 : Owner / Admin / Manager / Agent / Viewer).
Un même utilisateur peut appartenir à plusieurs organisations.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey

from app.core.database import Base
from app.models.distributor import GUID

VALID_ROLES = {"owner", "admin", "manager", "agent", "viewer"}


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    role = Column(String, default="owner")

    created_at = Column(DateTime, default=datetime.utcnow)
