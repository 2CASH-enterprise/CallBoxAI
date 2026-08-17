"""
Endpoints Calls — utilise les providers Mock par défaut (section 40.3).
Démontre le pipeline complet : appel -> agent IA -> base de connaissances ->
transfert éventuel -> transcript -> résumé -> stockage.
"""
import random
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.rag import retrieve_top_chunks
from app.models.call import Call
from app.models.agent import Agent
from app.providers.telephony.mock import MockTelephonyProvider
from app.providers.voice.mock import MockVoiceProvider
from app.providers.embeddings.mock import MockEmbeddingProvider

router = APIRouter()

telephony_provider = MockTelephonyProvider()
voice_provider = MockVoiceProvider()
embedding_provider = MockEmbeddingProvider()

# Probabilité qu'une conversation simulée nécessite un transfert humain, pour
# les agents ayant le transfert activé (section 8 et 11 du cahier des
# charges). En production, cette décision viendrait du LLM/de la conversation
# réelle, pas du hasard — cette simulation permet de tester tout le pipeline
# (statuts, dashboard, KPI "Transferts humains") sans compte Voice AI payant.
AUTO_TRANSFER_PROBABILITY = 0.3


class CallCreate(BaseModel):
    agent_id: uuid.UUID
    to_number: str
    from_number: str
    direction: str = "outbound"  # inbound | outbound


class TransferRequest(BaseModel):
    destination: str | None = None  # si omis, utilise agent.transfer_number


class CallOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    direction: str
    status: str
    provider: str
    provider_call_id: str | None
    transcript: str | None
    summary: str | None
    knowledge_context: str | None
    transferred_to: str | None
    transferred_at: datetime | None

    class Config:
        from_attributes = True


def get_call_or_404(call_id: uuid.UUID, organization_id: uuid.UUID, db: Session) -> Call:
    call = db.query(Call).filter(Call.id == call_id, Call.organization_id == organization_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Appel introuvable pour cette organisation")
    return call


@router.post("/calls", response_model=CallOut)
def create_call(
    payload: CallCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    agent = db.query(Agent).filter(
        Agent.id == payload.agent_id,
        Agent.organization_id == organization_id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable pour cette organisation")

    # 1. Déclenchement de l'appel (téléphonie)
    call_result = telephony_provider.make_call(
        to_number=payload.to_number,
        from_number=payload.from_number,
        agent_id=str(agent.id),
    )

    # 2. Consultation de la base de connaissances (RAG, section 10) — l'agent
    # récupère le contexte pertinent avant de démarrer la conversation.
    knowledge_query = agent.objective or agent.system_prompt or agent.name
    retrieved = retrieve_top_chunks(db, organization_id, knowledge_query, embedding_provider, top_k=1)
    knowledge_context = retrieved[0]["content"] if retrieved else None

    # 3. Conversation IA (voice provider)
    voice_provider.start_conversation(call_id=call_result["provider_call_id"], system_prompt=agent.system_prompt or "")
    transcript = voice_provider.get_transcript(call_result["provider_call_id"])
    summary = voice_provider.get_summary(call_result["provider_call_id"])

    if knowledge_context:
        transcript += (
            f"\n\n[Base de connaissances consultée — extrait de « {retrieved[0]['document_title']} »] "
            f"{knowledge_context}"
        )

    # 4. Décision de transfert vers un opérateur humain (section 8/11) — ne
    # se déclenche que si l'agent a le transfert activé ET un numéro configuré.
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

    # 5. Enregistrement en base
    call = Call(
        organization_id=organization_id,
        agent_id=agent.id,
        direction=payload.direction,
        status=status,
        provider="mock",
        provider_call_id=call_result["provider_call_id"],
        transcript=transcript,
        summary=summary,
        knowledge_context=knowledge_context,
        transferred_to=transferred_to,
        transferred_at=transferred_at,
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


@router.post("/calls/{call_id}/transfer", response_model=CallOut)
def transfer_call(
    call_id: uuid.UUID,
    payload: TransferRequest,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Transfert manuel d'un appel vers un opérateur humain, déclenché depuis le
    Dashboard (section 8/11/12). Utilise le numéro fourni, ou à défaut le
    numéro de transfert configuré sur l'agent de cet appel.
    """
    call = get_call_or_404(call_id, organization_id, db)
    agent = db.query(Agent).filter(Agent.id == call.agent_id).first()

    destination = payload.destination or (agent.transfer_number if agent else None)
    if not destination:
        raise HTTPException(
            status_code=400,
            detail="Aucun numéro de transfert : fournissez une destination ou configurez transfer_number sur l'agent.",
        )

    telephony_provider.transfer_call(call.provider_call_id, destination)

    call.status = "transferred"
    call.transferred_to = destination
    call.transferred_at = datetime.utcnow()
    call.transcript = (call.transcript or "") + f"\n\n[Transfert manuel vers un opérateur humain] Appel transféré vers {destination}."

    db.commit()
    db.refresh(call)
    return call


@router.get("/calls", response_model=list[CallOut])
def list_calls(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return db.query(Call).filter(Call.organization_id == organization_id).all()
