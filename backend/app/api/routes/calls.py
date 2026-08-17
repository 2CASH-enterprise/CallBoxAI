"""
Endpoints Calls.

Deux chemins bien distincts, à ne pas confondre (section 12/16/40) :

- POST /calls : SIMULATION du pipeline métier (Mock explicite, toujours,
  quels que soient les réglages de providers). Utile pour tester le CRM, les
  analytics, le transfert, le RAG — sans dépendre d'un vrai appel, qui est
  par nature asynchrone (dure plusieurs minutes) et ne peut donc jamais
  renvoyer un résultat immédiat comme le fait cet endpoint.

- POST /calls/real : déclenche un VRAI appel téléphonique (Twilio + Retell).
  Retourne immédiatement avec le statut "in_progress" ; le transcript, le
  résumé et le statut final arrivent plus tard via /webhooks/retell.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.config import settings
from app.core.call_pipeline import execute_mock_call, map_contact_status
from app.models.call import Call
from app.models.agent import Agent
from app.models.contact import Contact
from app.providers.telephony.mock import MockTelephonyProvider
from app.providers.voice.mock import MockVoiceProvider
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.providers.analytics.mock import MockAnalyticsProvider

router = APIRouter()

# Toujours Mock, volontairement — voir la note en tête de fichier. Ce ne sont
# PAS les mêmes instances que celles utilisées par /calls/real ou le Web Call.
mock_telephony_provider = MockTelephonyProvider()
mock_voice_provider = MockVoiceProvider()
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


def _get_agent_or_404(agent_id: uuid.UUID, organization_id: uuid.UUID, db: Session) -> Agent:
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.organization_id == organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable pour cette organisation")
    return agent


@router.post("/calls", response_model=CallOut)
def create_call(
    payload: CallCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """Simulation (section 40.3) — voir la note en tête de fichier."""
    agent = _get_agent_or_404(payload.agent_id, organization_id, db)

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
        telephony_provider=mock_telephony_provider,
        voice_provider=mock_voice_provider,
        embedding_provider=embedding_provider,
        analytics_provider=analytics_provider,
        direction=payload.direction,
        contact_id=payload.contact_id,
    )
    db.commit()
    db.refresh(call)
    return call


@router.post("/calls/real", response_model=CallOut)
def create_real_call(
    payload: CallCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Déclenche un VRAI appel téléphonique sortant (Twilio + Retell, section 16).
    Contrairement à /calls, celui-ci coûte réellement de l'argent — n'est
    utilisable que si Twilio ET Retell sont tous les deux configurés ET que
    l'agent a un agent Retell provisionné.

    L'appel prend plusieurs minutes en réalité : cet endpoint retourne
    immédiatement un Call au statut "in_progress" ; le transcript, le résumé
    et le statut final arrivent plus tard via /webhooks/retell.
    """
    agent = _get_agent_or_404(payload.agent_id, organization_id, db)

    if settings.telephony_provider != "twilio" or not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise HTTPException(
            status_code=400,
            detail="Twilio n'est pas configuré (TELEPHONY_PROVIDER=twilio + identifiants requis).",
        )
    if not settings.retell_api_key:
        raise HTTPException(status_code=400, detail="RETELL_API_KEY n'est pas configuré.")
    if not agent.retell_agent_id:
        raise HTTPException(
            status_code=400,
            detail="Cet agent n'a pas d'agent Retell provisionné (le provisionnement automatique a peut-être échoué).",
        )

    if payload.contact_id:
        contact = db.query(Contact).filter(
            Contact.id == payload.contact_id, Contact.organization_id == organization_id
        ).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    from app.providers.voice.retell_provider import RetellProvider

    provider = RetellProvider(api_key=settings.retell_api_key, agent_id=agent.retell_agent_id)
    result = provider.create_phone_call(
        to_number=payload.to_number,
        from_number=payload.from_number or settings.twilio_phone_number,
    )

    call = Call(
        organization_id=organization_id,
        agent_id=agent.id,
        contact_id=payload.contact_id,
        direction=payload.direction,
        status="in_progress",
        provider="retell",
        provider_call_id=result.get("call_id"),
        started_at=datetime.utcnow(),
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

    # Le transfert manuel utilise toujours le provider Mock pour rester
    # cohérent avec /calls (simulation) — un vrai transfert sur un appel réel
    # se ferait via l'API Retell/Twilio du provider concerné, à ajouter le
    # jour où /calls/real sera utilisé en production.
    mock_telephony_provider.transfer_call(call.provider_call_id, destination)

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
