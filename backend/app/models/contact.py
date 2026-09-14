"""
Contact CRM (section 18 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean

from app.core.database import Base
from app.models.distributor import GUID


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=True)
    status = Column(String, default="Nouveau")

    # Champs enrichis B2B (section 42/43) : traçabilité de la donnée,
    # nécessaire pour documenter la base légale d'un appel de prospection.
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    source = Column(String, nullable=True)  # provenance de la donnée (ex. "site web", "salon", "achat fichier")

    # Liste repoussoir (section 42/43, recommandation CNIL) : dès qu'une
    # personne exprime le souhait de ne plus être recontactée, plus AUCUNE
    # campagne future ne doit pouvoir l'appeler — vérifié par le Compliance
    # Check, indépendamment du marché ou de la catégorie d'agent.
    do_not_call = Column(Boolean, default=False)
    do_not_call_reason = Column(String, nullable=True)
    do_not_call_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
