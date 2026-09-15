"""
Journal des erreurs applicatives (monitoring Super Admin) — capture les
défaillances techniques (provisionnement d'agent, webhooks, outils en
temps réel...) pour un pilotage réel du produit, plutôt que de dépendre
uniquement des journaux serveur, jamais visibles depuis le dashboard.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean

from app.core.database import Base
from app.models.distributor import GUID


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=True)  # certaines erreurs sont globales, pas liées à un client

    source = Column(String, nullable=False)  # ex. "agent_provisioning", "facebook_webhook", "pms_tool", "unhandled_exception"
    message = Column(String, nullable=False)
    details = Column(Text, nullable=True)  # trace complète, si disponible

    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
