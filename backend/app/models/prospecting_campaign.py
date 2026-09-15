"""
Outil interne de prospection Super Admin (jamais visible des clients) —
générique par secteur, pas propre à l'hôtellerie : une campagne cible un
secteur donné (hôtellerie, centres de formation, cabinets médicaux...) et
propose le modèle d'agent adapté, avec un lot de cibles à démarcher.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer

from app.core.database import Base
from app.models.distributor import GUID


class ProspectingCampaign(Base):
    __tablename__ = "prospecting_campaigns"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)  # ex. "Hôtels lot 1"
    sector = Column(String, nullable=False)  # texte libre : "hôtellerie", "centres de formation"...
    agent_template_key = Column(String, nullable=False)  # quel modèle démontrer (voir lib/agentTemplates.ts côté frontend)

    created_at = Column(DateTime, default=datetime.utcnow)


# États possibles d'une cible, dans l'ordre attendu du parcours (section
# prospection hôtels/secteurs) — un simple champ String plutôt qu'un enum
# SQL, pour rester flexible si de nouveaux états s'ajoutent plus tard.
TARGET_STATUSES = [
    "imported", "analyzed", "agent_created", "email_prepared",
    "sent", "opened", "clicked", "page_visited", "called", "converted",
]


class ProspectingTarget(Base):
    __tablename__ = "prospecting_targets"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(GUID(), ForeignKey("prospecting_campaigns.id"), nullable=False)

    company_name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    website_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)  # directeur/propriétaire, si trouvé

    status = Column(String, default="imported")

    # Rempli à l'étape "analyse du site web" (à venir) : texte brut extrait,
    # relu par un humain avant la suite (vérification humaine validée).
    extracted_info = Column(Text, nullable=True)

    # Rempli à l'étape "création de l'agent" (à venir)
    demo_agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=True)
    demo_page_slug = Column(String, nullable=True, unique=True)

    # Rempli à l'étape "préparation de l'email" (à venir) — jamais envoyé
    # automatiquement, un bouton d'envoi par cible reste nécessaire.
    email_subject = Column(String, nullable=True)
    email_body = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
