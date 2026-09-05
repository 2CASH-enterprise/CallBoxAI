"""
Campagne d'appels sortants (section 13 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer

from app.core.database import Base
from app.models.distributor import GUID


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=False)

    name = Column(String, nullable=False)
    status = Column(String, default="draft")  # draft | running | paused | completed

    # Horaires d'appel autorisés, ex. "08:00" / "19:00" (section 13 du cahier des charges)
    schedule_start = Column(String, default="08:00")
    schedule_end = Column(String, default="19:00")

    # Marché ciblé (section 42/43 — brique de compliance) : détermine les
    # règles légales à appliquer automatiquement (horaires de démarchage,
    # obligation de consentement B2C...) — voir app.core.compliance.
    # None = aucun profil légal spécifique appliqué (marché non couvert).
    target_market = Column(String, nullable=True)

    # Nombre de tentatives max par contact avant abandon définitif (retry, section 13)
    max_attempts = Column(Integer, default=3)

    # Nombre de RELANCES max par contact JOINT mais pas encore converti (ni
    # rendez-vous pris, ni refus définitif) — distinct de max_attempts qui ne
    # concerne que les contacts injoignables.
    max_follow_ups = Column(Integer, default=2)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)


class CampaignTarget(Base):
    """Un contact à appeler dans le cadre d'une campagne, avec son statut d'avancement."""

    __tablename__ = "campaign_targets"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(GUID(), ForeignKey("campaigns.id"), nullable=False)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=False)
    call_id = Column(GUID(), ForeignKey("calls.id"), nullable=True)

    status = Column(String, default="pending")  # pending | completed | no_answer | failed
    attempts = Column(Integer, default=0)

    # Relance basée sur l'intérêt (pas seulement la joignabilité) : nombre de
    # relances déjà effectuées pour ce contact, et date à partir de laquelle
    # la prochaine relance est autorisée (délai minimum entre deux appels au
    # même contact — évite de rappeler deux fois dans la même minute).
    follow_up_count = Column(Integer, default=0)
    next_attempt_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
