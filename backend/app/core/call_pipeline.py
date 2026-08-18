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
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.rag import retrieve_top_chunks
from app.models.agent import Agent
from app.models.call import Call
from app.models.contact import Contact
from app.models.appointment import Appointment
from app.providers.telephony.base import TelephonyProvider
from app.providers.voice.base import VoiceProvider
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.analytics.base import AnalyticsProvider

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
    """
    call_result = telephony_provider.make_call(to_number=to_number, from_number=from_number, agent_id=str(agent.id))

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
