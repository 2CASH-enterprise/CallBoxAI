"""
Journal d'audit de conformité (section 42/43 du cahier des charges) — une
ligne à CHAQUE vérification du Compliance Check, autorisée ou bloquée, pour
pouvoir reconstruire précisément "pourquoi cet appel a été autorisé" en cas
de contrôle. Jamais modifié après coup, uniquement des ajouts (append-only),
comme le Consent Ledger.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean

from app.core.database import Base
from app.models.distributor import GUID


class ComplianceAuditLog(Base):
    __tablename__ = "compliance_audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=False)
    campaign_id = Column(GUID(), ForeignKey("campaigns.id"), nullable=True)

    decision = Column(String, nullable=False)  # "allowed" | "blocked"
    reason = Column(String, nullable=False)  # motif lisible (ex. "Consentement absent", "Liste repoussoir")
    legal_basis = Column(String, nullable=True)  # ex. "intérêt légitime (B2B)", "consentement (B2C)"

    created_at = Column(DateTime, default=datetime.utcnow)
