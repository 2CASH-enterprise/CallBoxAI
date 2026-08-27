"""
Endpoints Agents IA — toujours filtrés par organization_id (isolation multi-tenant,
section 3 du cahier des charges).
"""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access, get_current_user
from app.core.config import settings
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.agent_request import AgentRequest, VALID_STATUSES as AGENT_REQUEST_STATUSES
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentCreate(BaseModel):
    name: str
    objective: str | None = None
    language: str = "fr"
    system_prompt: str | None = None
    transfer_enabled: bool = False
    transfer_number: str | None = None
    transfer_instructions: str | None = None
    voice_id: str | None = None
    business_hours_start: str | None = None
    business_hours_end: str | None = None
    ticketing_enabled: bool = False
    pms_enabled: bool = False
    kyc_enabled: bool = False
    kyc_link_url: str | None = None
    category: str = "generique"
    source_template: str | None = None
    whatsapp_enabled: bool = False
    meeting_booking_enabled: bool = False


class AgentUpdate(BaseModel):
    name: str | None = None
    objective: str | None = None
    language: str | None = None
    system_prompt: str | None = None
    transfer_enabled: bool | None = None
    transfer_number: str | None = None
    transfer_instructions: str | None = None
    voice_id: str | None = None
    business_hours_start: str | None = None
    business_hours_end: str | None = None
    ticketing_enabled: bool | None = None
    pms_enabled: bool | None = None
    kyc_enabled: bool | None = None
    kyc_link_url: str | None = None
    category: str | None = None
    source_template: str | None = None
    whatsapp_enabled: bool | None = None
    meeting_booking_enabled: bool | None = None


class AgentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    objective: str | None = None
    language: str
    system_prompt: str | None = None
    transfer_enabled: bool
    transfer_number: str | None
    transfer_instructions: str | None
    retell_agent_id: str | None
    voice_id: str | None
    business_hours_start: str | None
    business_hours_end: str | None
    ticketing_enabled: bool
    pms_enabled: bool
    kyc_enabled: bool
    kyc_link_url: str | None
    category: str
    source_template: str | None
    whatsapp_enabled: bool
    meeting_booking_enabled: bool

    class Config:
        from_attributes = True


class WebCallOut(BaseModel):
    access_token: str
    call_id: str


def _provision_retell_agent_if_configured(agent: Agent, db: Session) -> None:
    """
    Crée (ou MET À JOUR si l'agent a déjà été provisionné) l'agent
    correspondant côté Retell (section 16), de façon invisible pour le
    client — voir RetellProvider.provision_agent(). Mettre à jour plutôt que
    recréer évite d'accumuler des agents Retell orphelins à chaque
    modification (voix, prompt...).

    Résilience (section 29) : si Retell est injoignable ou en erreur, on ne
    bloque JAMAIS la création/modification de l'agent CallBoxAI — on
    journalise et on laisse retell_agent_id inchangé ; le client peut
    continuer à travailler (base de connaissances, campagnes...) même sans
    agent vocal à jour, et un administrateur pourra relancer plus tard.
    """
    if settings.voice_provider != "retell" or not settings.retell_api_key:
        return

    organization = db.query(Organization).filter(Organization.id == agent.organization_id).first()
    knowledge_base_id = organization.retell_knowledge_base_id if organization else None

    logger.info(
        "Provisionnement Retell démarré : agent=%s pms_enabled=%s category=%s "
        "public_base_url=%r existing_agent_id=%r existing_llm_id=%r knowledge_base_id=%r",
        agent.id, agent.pms_enabled, agent.category,
        settings.public_base_url, agent.retell_agent_id, agent.retell_llm_id, knowledge_base_id,
    )

    try:
        from app.providers.voice.retell_provider import RetellProvider

        provider = RetellProvider(api_key=settings.retell_api_key, agent_id="")
        result = provider.provision_agent(
            name=agent.name,
            system_prompt=agent.system_prompt or "",
            language=agent.language,
            model=settings.retell_default_llm_model,
            voice_id=agent.voice_id or settings.retell_default_voice_id,
            pms_enabled=agent.pms_enabled,
            kyc_enabled=agent.kyc_enabled,
            whatsapp_enabled=agent.whatsapp_enabled,
            meeting_booking_enabled=agent.meeting_booking_enabled,
            callboxai_agent_id=str(agent.id),
            organization_id=str(agent.organization_id),
            existing_agent_id=agent.retell_agent_id,
            existing_llm_id=agent.retell_llm_id,
            public_base_url=settings.public_base_url or None,
            knowledge_base_id=knowledge_base_id,
        )
        agent.retell_agent_id = result["agent_id"]
        agent.retell_llm_id = result["llm_id"]
        logger.info(
            "Provisionnement Retell terminé avec succès : agent=%s retell_agent_id=%s retell_llm_id=%s",
            agent.id, result["agent_id"], result["llm_id"],
        )
    except Exception:
        logger.exception("Échec du provisionnement automatique de l'agent Retell pour l'agent %s", agent.id)


def _create_agent_for_organization(db: Session, organization_id: uuid.UUID, payload: AgentCreate) -> Agent:
    """
    Logique de création partagée entre le client (POST /agents, restreint à
    sa propre organisation) et le Super Admin (POST /admin/agent-requests/
    {id}/fulfill, pour n'importe quelle organisation — section 41 : demande
    de création plutôt que self-service, pour mieux calibrer le prompt).
    """
    agent = Agent(organization_id=organization_id, **payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)

    _provision_retell_agent_if_configured(agent, db)
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/agents", response_model=AgentOut)
def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return _create_agent_for_organization(db, organization_id, payload)


@router.get("/agents", response_model=list[AgentOut])
def list_agents(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return db.query(Agent).filter(Agent.organization_id == organization_id).all()


def _update_agent(db: Session, agent: Agent, payload: AgentUpdate) -> Agent:
    """
    Logique de mise à jour partagée entre le client (PATCH /agents/{id},
    restreint à sa propre organisation) et le Super Admin (PATCH
    /admin/agents/{id}, n'importe quelle organisation — section 41 : les
    agents sont créés pour le compte du client, il faut pouvoir les corriger
    après coup, notamment le prompt).
    """
    updates = payload.model_dump(exclude_unset=True)
    needs_reprovision = any(field in updates for field in ("voice_id", "system_prompt", "language", "name", "pms_enabled", "kyc_enabled", "kyc_link_url", "whatsapp_enabled", "meeting_booking_enabled"))

    for field, value in updates.items():
        setattr(agent, field, value)

    if needs_reprovision:
        _provision_retell_agent_if_configured(agent, db)

    db.commit()
    db.refresh(agent)
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Met à jour un agent — notamment utile pour changer la voix (voice_id)
    après coup, sans recréer l'agent. Si la voix, le prompt ou la langue
    changent, l'agent Retell est re-provisionné automatiquement.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.organization_id == organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable pour cette organisation")
    return _update_agent(db, agent, payload)


@router.post("/agents/{agent_id}/test-call", response_model=WebCallOut)
def create_test_web_call(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Démarre une session de test vocal en direct (Web Call, section 16) pour
    cet agent, via le navigateur — sans passer par Twilio ni par un numéro
    de téléphone. Utilise l'agent Retell provisionné automatiquement à la
    création (ou RETELL_AGENT_ID global en secours).
    """
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.organization_id == organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable pour cette organisation")

    if not settings.retell_api_key:
        raise HTTPException(
            status_code=400,
            detail="RETELL_API_KEY n'est pas configuré sur le serveur. Renseignez-le pour activer le test vocal.",
        )

    effective_retell_agent_id = agent.retell_agent_id or settings.retell_agent_id
    if not effective_retell_agent_id:
        raise HTTPException(
            status_code=400,
            detail="Aucun agent Retell associé pour l'instant (le provisionnement automatique a peut-être échoué — réessayez ou contactez le support).",
        )

    from app.providers.voice.retell_provider import RetellProvider

    provider = RetellProvider(api_key=settings.retell_api_key, agent_id=effective_retell_agent_id)
    result = provider.create_web_call(agent_id=effective_retell_agent_id)

    # Sans cette ligne, le webhook /webhooks/retell n'aurait rien à
    # compléter à la fin du test (section 16/30) : ni transcript, ni
    # classification, ni ticket — le test vocal resterait invisible partout
    # ailleurs dans le dashboard.
    from app.models.call import Call

    db.add(
        Call(
            organization_id=organization_id,
            agent_id=agent.id,
            direction="inbound",
            status="in_progress",
            provider="retell",
            provider_call_id=result["call_id"],
            started_at=datetime.utcnow(),
        )
    )
    db.commit()

    return WebCallOut(access_token=result["access_token"], call_id=result["call_id"])


# ---------- Demandes de création d'agent (section 41) ----------
# Le client ne crée plus lui-même son agent (voir décision produit) : il
# décrit son besoin, le Super Admin le configure et le crée pour lui — voir
# app.api.routes.admin pour le traitement côté Super Admin.

class AgentRequestCreate(BaseModel):
    use_case: str
    objective: str


class AgentRequestOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    use_case: str
    objective: str
    status: str
    admin_notes: str | None
    created_agent_id: uuid.UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/agent-requests", response_model=AgentRequestOut)
def create_agent_request(
    payload: AgentRequestCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
    current_user: User = Depends(get_current_user),
):
    request = AgentRequest(
        organization_id=organization_id,
        requested_by_user_id=current_user.id,
        use_case=payload.use_case,
        objective=payload.objective,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/agent-requests", response_model=list[AgentRequestOut])
def list_agent_requests(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return (
        db.query(AgentRequest)
        .filter(AgentRequest.organization_id == organization_id)
        .order_by(AgentRequest.created_at.desc())
        .all()
    )
