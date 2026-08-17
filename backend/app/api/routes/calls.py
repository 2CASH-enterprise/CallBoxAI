"""
Endpoints Calls — utilise les providers Mock par défaut (section 40.3).
Démontre le pipeline complet : appel -> agent IA -> transcript -> résumé -> stockage.
"""
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


class CallCreate(BaseModel):
    agent_id: uuid.UUID
    to_number: str
    from_number: str
    direction: str = "outbound"  # inbound | outbound


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

    class Config:
        from_attributes = True


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

    # 4. Enregistrement en base
    call = Call(
        organization_id=organization_id,
        agent_id=agent.id,
        direction=payload.direction,
        status="completed",
        provider="mock",
        provider_call_id=call_result["provider_call_id"],
        transcript=transcript,
        summary=summary,
        knowledge_context=knowledge_context,
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


@router.get("/calls", response_model=list[CallOut])
def list_calls(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return db.query(Call).filter(Call.organization_id == organization_id).all()
