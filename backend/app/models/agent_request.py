"""
Demande de création d'agent (section 41 du cahier des charges) — le client
ne crée plus lui-même son agent, il décrit son besoin, et le Super Admin le
configure et le crée pour lui. Objectif : éviter un agent mal calibré
(prompt, catégorie, réglages) livré sans supervision.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text

from app.core.database import Base
from app.models.distributor import GUID

VALID_STATUSES = {"pending", "in_progress", "completed", "rejected"}


class AgentRequest(Base):
    __tablename__ = "agent_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    requested_by_user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)

    use_case = Column(String, nullable=False)  # ex. "hotellerie", "prospection", "autre"
    objective = Column(Text, nullable=False)  # description libre du besoin par le client
    status = Column(String, default="pending")
    admin_notes = Column(Text, nullable=True)  # visible par le client, ex. motif de refus

    created_agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
