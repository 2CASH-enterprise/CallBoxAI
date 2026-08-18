"""
Pipeline d'appel partagé (sections 12, 13, 19 du cahier des charges).

Centralise la logique commune entre l'appel manuel (/calls) et le traitement
de campagnes (/campaigns/.../run-batch) : téléphonie, consultation RAG,
décision de transfert, classification analytics, et mise à jour automatique
du statut CRM du contact concerné (section 18 : "chaque appel doit pouvoir
modifier automatiquement le statut" du contact).
"""
import random
import uuid
from datetime import datetime, timedelta, time

from sqlalchemy.orm import Session

from app.core.rag import retrieve_top_chunks
from app.models.agent import Agent
from app.models.call import Call
from app.models.contact import Contact
from app.models.appointment import Appointment
from app.models.message import Message
from app.providers.telephony.base import TelephonyProvider
from app.providers.voice.base import VoiceProvider
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.analytics.base import AnalyticsProvider

# Probabilité qu'un appel entrant hors horaires laisse un message "urgent"
# (télé-secrétariat, section 12). Simulation — en production, ce serait
# évalué par le LLM à partir du contenu réel de la demande.
URGENT_MESSAGE_PROBABILITY = 0.2

MOCK_MESSAGE_CONTENTS = [
    "Souhaite être rappelé(e) au sujet d'une demande de devis.",
    "Appelle pour un suivi de dossier en cours.",
    "Demande d'information générale sur les services proposés.",
    "Souhaite reprogrammer un rendez-vous existant.",
    "Réclamation à traiter en priorité.",
]

# Probabilité qu'une conversation simulée nécessite un transfert humain, pour
# les agents ayant le transfert activé (section 8 et 11). En production,
# cette décision viendrait du LLM/de la conversation réelle, pas du hasard.
AUTO_TRANSFER_PROBABILITY = 0.3


def map_contact_status(qualification: str | None, action_taken: str | None) -> str:
    """Traduit le résultat de l'appel en statut CRM (section 18)."""
    if action_taken == "Rendez-vous pris":
        return "RDV"
    if qualification == "Pas intéressé":
        return "Pas intéressé"
    if qualification == "À suivre par un humain":
        return "À rappeler"
    if qualification in ("Prospect chaud", "Prospect tiède"):
        return "Intéressé"
    return "Contacté"


def _generate_mock_slot() -> datetime:
    """
    Simule un créneau de rendez-vous proposé par l'agent (2 à 6 jours plus
    tard, sur une plage horaire de bureau 9h-17h). En production, ce serait
    déterminé par la disponibilité réelle (agenda connecté), pas simulé.
    """
    days_ahead = random.randint(2, 6)
    hour = random.choice([9, 10, 11, 14, 15, 16])
    slot = datetime.utcnow() + timedelta(days=days_ahead)
    return slot.replace(hour=hour, minute=random.choice([0, 30]), second=0, microsecond=0)


def is_within_business_hours(agent: Agent, now: datetime | None = None) -> bool:
    """
    Télé-secrétariat (section 12) : un agent sans horaires configurés est
    considéré disponible en permanence. Sinon, hors de la plage définie, un
    appel entrant déclenche une prise de message plutôt qu'une conversation.
    """
    if not agent.business_hours_start or not agent.business_hours_end:
        return True
    now = now or datetime.utcnow()
    start = time.fromisoformat(agent.business_hours_start)
    end = time.fromisoformat(agent.business_hours_end)
    current = now.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end  # fenêtre à cheval sur minuit


def execute_mock_call(
    db: Session,
    organization_id: uuid.UUID,
    agent: Agent,
    to_number: str,
    from_number: str,
    telephony_provider: TelephonyProvider,
    voice_provider: VoiceProvider,
    embedding_provider: EmbeddingProvider,
    analytics_provider: AnalyticsProvider,
    direction: str = "outbound",
    contact_id: uuid.UUID | None = None,
) -> Call:
    """
    Exécute un appel simulé complet (téléphonie -> RAG -> conversation ->
    transfert éventuel -> classification -> mise à jour CRM) et retourne
    l'objet Call. Ajouté à la session mais PAS committé : au code appelant de
    committer, ce qui permet de traiter un lot entier en une seule transaction
    (section 13/14 — campagnes).

    Télé-secrétariat (section 12) : un appel ENTRANT reçu hors des horaires
    d'ouverture de l'agent bascule automatiquement vers une prise de message
    structurée, plutôt qu'une conversation normale (personne n'étant
    disponible pour un transfert ou un rendez-vous en dehors des heures).
    """
    call_result = telephony_provider.make_call(to_number=to_number, from_number=from_number, agent_id=str(agent.id))

    if direction == "inbound" and not is_within_business_hours(agent):
        transcript = (
            f"Agent : Bonjour, vous êtes bien chez {agent.name.replace('Agent ', '')}. "
            "Nos bureaux sont actuellement fermés, souhaitez-vous laisser un message ?\n"
            "Client : Oui, merci."
        )
        content = random.choice(MOCK_MESSAGE_CONTENTS)
        urgent = random.random() < URGENT_MESSAGE_PROBABILITY

        call = Call(
            organization_id=organization_id,
            agent_id=agent.id,
            contact_id=contact_id,
            direction=direction,
            status="message_taken",
            provider="mock",
            provider_call_id=call_result["provider_call_id"],
            transcript=transcript,
            summary=f"Message pris hors horaires : {content}",
            action_taken="Message pris",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
        )
        db.add(call)
        db.flush()

        contact = db.query(Contact).filter(Contact.id == contact_id).first() if contact_id else None
        message = Message(
            organization_id=organization_id,
            agent_id=agent.id,
            call_id=call.id,
            contact_id=contact_id,
            caller_phone=from_number,
            caller_name=(f"{contact.first_name or ''} {contact.last_name or ''}".strip() or None) if contact else None,
            content=content,
            urgent=urgent,
            callback_requested=True,
            status="new",
        )
        db.add(message)
        if contact:
            contact.status = "À rappeler"

        return call

    # Consultation de la base de connaissances (RAG, section 10)
    knowledge_query = agent.objective or agent.system_prompt or agent.name
    retrieved = retrieve_top_chunks(db, organization_id, knowledge_query, embedding_provider, top_k=1)
    knowledge_context = retrieved[0]["content"] if retrieved else None

    voice_provider.start_conversation(call_result["provider_call_id"], agent.system_prompt or "")
    transcript = voice_provider.get_transcript(call_result["provider_call_id"])
    summary = voice_provider.get_summary(call_result["provider_call_id"])

    if knowledge_context:
        transcript += (
            f"\n\n[Base de connaissances consultée — extrait de « {retrieved[0]['document_title']} »] "
            f"{knowledge_context}"
        )

    # Décision de transfert (section 8/11)
    status = "completed"
    transferred_to = None
    transferred_at = None

    if agent.transfer_enabled and agent.transfer_number and random.random() < AUTO_TRANSFER_PROBABILITY:
        telephony_provider.transfer_call(call_result["provider_call_id"], agent.transfer_number)
        status = "transferred"
        transferred_to = agent.transfer_number
        transferred_at = datetime.utcnow()
        reason = agent.transfer_instructions or "demande dépassant les compétences de l'agent"
        transcript += f"\n\n[Transfert vers un opérateur humain — {reason}] Appel transféré vers {agent.transfer_number}."

    # Classification analytics (section 19)
    classification = analytics_provider.classify(transcript=transcript, summary=summary, status=status)

    call = Call(
        organization_id=organization_id,
        agent_id=agent.id,
        contact_id=contact_id,
        direction=direction,
        status=status,
        provider="mock",
        provider_call_id=call_result["provider_call_id"],
        transcript=transcript,
        summary=summary,
        knowledge_context=knowledge_context,
        transferred_to=transferred_to,
        transferred_at=transferred_at,
        intent=classification["intent"],
        qualification=classification["qualification"],
        sentiment=classification["sentiment"],
        score=classification["score"],
        action_taken=classification["action_taken"],
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    db.add(call)
    db.flush()

    # Mise à jour automatique du statut CRM du contact (section 18)
    appointment = None
    if contact_id:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if contact:
            contact.status = map_contact_status(classification["qualification"], classification["action_taken"])

        # Prise de rendez-vous réelle (section 30 : POST /appointments), pas
        # seulement une étiquette — utile pour la prospection commerciale.
        if classification["action_taken"] == "Rendez-vous pris":
            appointment = Appointment(
                organization_id=organization_id,
                contact_id=contact_id,
                agent_id=agent.id,
                call_id=call.id,
                scheduled_at=_generate_mock_slot(),
                status="scheduled",
                notes=f"Rendez-vous pris automatiquement suite à l'appel du {call.started_at:%d/%m/%Y}.",
            )
            db.add(appointment)

    return call
