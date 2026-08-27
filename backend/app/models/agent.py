"""
Agent IA (section 8 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean

from app.core.database import Base
from app.models.distributor import GUID


class Agent(Base):
    __tablename__ = "agents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    name = Column(String, nullable=False)
    objective = Column(String, nullable=True)
    language = Column(String, default="fr")
    system_prompt = Column(Text, nullable=True)

    # Règles de transfert vers un opérateur humain (section 8 et 11 du cahier
    # des charges) : numéro/poste à joindre, et instructions optionnelles
    # décrivant dans quels cas transférer (ex. "demande hors compétence").
    transfer_enabled = Column(Boolean, default=False)
    transfer_number = Column(String, nullable=True)
    transfer_instructions = Column(Text, nullable=True)

    # ID de l'agent créé côté Retell (dans leur dashboard), utilisé pour le
    # test vocal en direct via Web Call (section 16 — intégration réelle).
    # Optionnel : si vide, on retombe sur RETELL_AGENT_ID (configuration
    # globale) si défini.
    retell_agent_id = Column(String, nullable=True)
    # ID du LLM Retell associé — nécessaire pour METTRE À JOUR l'agent
    # existant plutôt que d'en recréer un nouveau à chaque modification
    # (voix, prompt...), voir RetellProvider.provision_agent().
    retell_llm_id = Column(String, nullable=True)

    # Voix à utiliser pour cet agent (ex. "11labs-Charlotte", récupéré dans
    # l'onglet "Voices" du dashboard Retell). Optionnel : si vide, la voix
    # par défaut de la plateforme (RETELL_DEFAULT_VOICE_ID) est utilisée.
    voice_id = Column(String, nullable=True)

    # Horaires d'ouverture (télé-secrétariat) : en dehors de cette plage, un
    # appel entrant déclenche une prise de message plutôt qu'une conversation
    # normale (section 12 : service client de niveau 1). Si les deux champs
    # sont vides, l'agent est considéré disponible en permanence.
    business_hours_start = Column(String, nullable=True)  # ex. "08:00"
    business_hours_end = Column(String, nullable=True)  # ex. "18:00"

    # Service client (section 1 et 12 du cahier des charges) : quand activé,
    # chaque appel entrant (dans les horaires) génère automatiquement un
    # ticket de suivi (catégorie, priorité, statut), plutôt que de rester un
    # simple transcript non exploité.
    ticketing_enabled = Column(Boolean, default=False)

    # PMS (Property Management System, section 5/16 du cahier des charges) :
    # quand activé, l'agent peut consulter la disponibilité et créer une
    # réservation EN DIRECT pendant l'appel réel (via les outils Retell), pas
    # seulement depuis le dashboard. Sans intérêt pour un agent non-hôtelier.
    pms_enabled = Column(Boolean, default=False)

    # KYC simplifié (section 41) : plutôt que de construire un système de
    # vérification de documents, on envoie simplement au client le lien du
    # KYC déjà existant chez le partenaire (opérateur télécom, banque...).
    kyc_enabled = Column(Boolean, default=False)
    kyc_link_url = Column(String, nullable=True)

    # Traçabilité (section 41) : de quel modèle cet agent a été créé au
    # départ — PAS un lien vivant, juste une étiquette. Modifier le modèle
    # ne modifie jamais cet agent automatiquement (isolation multi-tenant) ;
    # sert uniquement à afficher "Récupérer la dernière version du modèle"
    # côté Super Admin, pour comparer/rafraîchir manuellement si besoin.
    source_template = Column(String, nullable=True)

    # Prospection commerciale B2C/B2B (section 42) : envoi automatique
    # d'une brochure/offre par WhatsApp si le prospect montre de l'intérêt,
    # et réservation directe d'un rendez-vous en direct pendant l'appel
    # (B2B uniquement — en B2C, l'intérêt est transmis à un commercial qui
    # rappelle, l'IA ne réserve jamais de RDV elle-même).
    whatsapp_enabled = Column(Boolean, default=False)
    meeting_booking_enabled = Column(Boolean, default=False)

    # Métier de l'agent (section 19/41) : adapte le VOCABULAIRE affiché de la
    # classification automatique ("Prospect tiède" n'a aucun sens pour un
    # client d'hôtel) — voir app.core.classification_labels. La logique
    # métier (CRM, rendez-vous, relances) reste identique quelle que soit
    # la catégorie ; seul l'habillage change.
    category = Column(String, default="generique")  # generique|prospection|service_client|hotellerie|telesecretariat

    created_at = Column(DateTime, default=datetime.utcnow)
