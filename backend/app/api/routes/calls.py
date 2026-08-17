"""
Endpoints Calls — utilise les providers Mock par défaut (section 40.3).
Démontre le pipeline complet : appel -> agent IA -> transcript -> résumé -> stockage.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.call import Call
from app.models.agent import Agent
from app.providers.telephony.mock import MockTelephonyProvider
from app.providers.voice.mock import MockVoiceProvider

router = APIRouter()

telephony_provider = MockTelephonyProvider()
voice_provider = MockVoiceProvider()


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

    class Config:
        from_attributes = True


def get_organization_id(x_organization_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="x-organization-id invalide")


@router.post("/calls", response_model=CallOut)
def create_call(
    payload: CallCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
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

    # 2. Conversation IA (voice provider)
    voice_provider.start_conversation(call_id=call_result["provider_call_id"], system_prompt=agent.system_prompt or "")
    transcript = voice_provider.get_transcript(call_result["provider_call_id"])
    summary = voice_provider.get_summary(call_result["provider_call_id"])

    # 3. Enregistrement en base
    call = Call(
        organization_id=organization_id,
        agent_id=agent.id,
        direction=payload.direction,
        status="completed",
        provider="mock",
        provider_call_id=call_result["provider_call_id"],
        transcript=transcript,
        summary=summary,
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
    organization_id: uuid.UUID = Depends(get_organization_id),
):
    return db.query(Call).filter(Call.organization_id == organization_id).all()
