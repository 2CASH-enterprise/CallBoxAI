"""
Équipe d'agents (section 40 — palier "Growth", "Employé IA") : regroupement
librement composé par le client de plusieurs de ses agents déjà créés, sous
un nom personnalisé ("Mon équipe commerciale"...) — sert uniquement à la
présentation combinée (résumé unique, plutôt que des vues séparées par
agent), aucune conséquence technique sur le fonctionnement des agents.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey

from app.core.database import Base
from app.models.distributor import GUID


class AgentTeam(Base):
    __tablename__ = "agent_teams"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
