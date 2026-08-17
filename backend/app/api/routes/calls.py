"""
Endpoints Calls — utilise les providers Mock par défaut (section 40.3).
La logique du pipeline d'appel (téléphonie, RAG, transfert, classification,
mise à jour CRM) est centralisée dans app.core.call_pipeline, partagée avec
le traitement de campagnes (section 13).
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.call_pipeline import execute_mock_call, map_contact_status
from app.models.call import Call
from app.models.agent import Agent
from app.models.contact import Contact
from app.core.providers import get_telephony_provider, get_voice_provider
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.analytics.mock import MockAnalyticsProvider

router = APIRouter()

telephony_provider = get_telephony_provider()
voice_provider = get_voice_provider()
embedding_provider = MockEmbeddingProvider()
analytics_provider = MockAnalyticsProvider()


class CallCreate(BaseModel):
    agent_id: uuid.UUID
    to_number: str
    from_number: str
    direction: str = "outbound"  # inbound | outbound
    contact_id: uuid.UUID | None = None  # si fourni, met à jour son statut CRM (section 18)


class TransferRequest(BaseModel):
    destination: str | None = None  # si omis, utilise agent.transfer_number


class CallOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    contact_id: uuid.UUID | None
    direction: str
    status: str
    provider: str
    provider_call_id: str | None
    transcript: str | None
    summary: str | None
    knowledge_context: str | None
    transferred_to: str | None
    transferred_at: datetime | None
    intent: str | None
    qualification: str | None
    sentiment: str | None
    score: int | None
    action_taken: str | None

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

    if payload.contact_id:
        contact = db.query(Contact).filter(
            Contact.id == payload.contact_id, Contact.organization_id == organization_id
        ).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    call = execute_mock_call(
        db=db,
        organization_id=organization_id,
        agent=agent,
        to_number=payload.to_number,
        from_number=payload.from_number,
        telephony_provider=telephony_provider,
        voice_provider=voice_provider,
        embedding_provider=embedding_provider,
        analytics_provider=analytics_provider,
        direction=payload.direction,
        contact_id=payload.contact_id,
    )
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
    call.qualification = "À suivre par un humain"
    call.action_taken = "Transfert vers opérateur"

    if call.contact_id:
        contact = db.query(Contact).filter(Contact.id == call.contact_id).first()
        if contact:
            contact.status = map_contact_status(call.qualification, call.action_taken)

    db.commit()
    db.refresh(call)
    return call


@router.get("/calls", response_model=list[CallOut])
def list_calls(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return db.query(Call).filter(Call.organization_id == organization_id).all()
