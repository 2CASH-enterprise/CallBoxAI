"""
Utilisateur (section 6.1 et 24 du cahier des charges).

Deux niveaux de rôles distincts :
- Rôles plateforme (is_super_admin / distributor_id) : globaux, transverses.
- Rôles par organisation : voir OrganizationMembership (owner/admin/manager/agent/viewer).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey

from app.core.database import Base
from app.models.distributor import GUID


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)

    # Rôle plateforme "Super Admin" (section 6.1) — accès total.
    is_super_admin = Column(Boolean, default=False)

    # Si non nul : ce compte EST le login d'un distributeur (section 39).
    # Un utilisateur est soit un membre d'organisation(s), soit un distributeur,
    # soit un Super Admin — rarement plusieurs à la fois en pratique.
    distributor_id = Column(GUID(), ForeignKey("distributors.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
