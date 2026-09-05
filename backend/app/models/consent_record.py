"""
Registre de consentement (section 42/43 du cahier des charges) — preuve
horodatée et immuable qu'un contact a explicitement accepté d'être appelé,
nécessaire pour la prospection B2C conforme (nouvelle réglementation
française du 11 août 2026 : opt-in obligatoire en B2C, contrairement au B2B
qui reste sous "intérêt légitime").

Immuable par conception : une fois créé, un enregistrement de consentement
n'est JAMAIS modifié ni supprimé — seul un champ revoked_at peut être
renseigné après coup, pour tracer un retrait sans jamais réécrire l'histoire
(texte exact affiché, date, source d'origine restent intacts pour servir de
preuve en cas de contrôle).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey

from app.core.database import Base
from app.models.distributor import GUID


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=False)

    source = Column(String, nullable=False)  # ex. "facebook_lead_ads", "import_manuel", "formulaire_web"
    campaign_reference = Column(String, nullable=True)  # ex. identifiant de la publicité/campagne d'origine
    consent_text = Column(Text, nullable=False)  # texte EXACT affiché au moment du consentement — preuve

    consented_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)  # seul champ modifiable après création
