"""
Endpoints Agents IA — toujours filtrés par organization_id (isolation multi-tenant,
section 3 du cahier des charges).
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.config import settings
from app.models.agent import Agent

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


class AgentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    objective: str | None = None
    language: str
    transfer_enabled: bool
    transfer_number: str | None
    transfer_instructions: str | None
    retell_agent_id: str | None
    voice_id: str | None
    business_hours_start: str | None
    business_hours_end: str | None

    class Config:
        from_attributes = True


class WebCallOut(BaseModel):
    access_token: str
    call_id: str


def _provision_retell_agent_if_configured(agent: Agent) -> None:
    """
    Crée automatiquement l'agent correspondant côté Retell (section 16), de
    façon invisible pour le client — voir RetellProvider.provision_agent().

    Résilience (section 29) : si Retell est injoignable ou en erreur, on ne
    bloque JAMAIS la création de l'agent CallBoxAI — on journalise et on
    laisse retell_agent_id vide ; le client peut continuer à travailler
    (base de connaissances, campagnes...) même sans agent vocal actif, et un
    administrateur pourra relancer le provisionnement plus tard.
    """
    if settings.voice_provider != "retell" or not settings.retell_api_key:
        return

    try:
        from app.providers.voice.retell_provider import RetellProvider

        provider = RetellProvider(api_key=settings.retell_api_key, agent_id="")
        agent.retell_agent_id = provider.provision_agent(
            name=agent.name,
            system_prompt=agent.system_prompt or "",
            language=agent.language,
            model=settings.retell_default_llm_model,
            voice_id=agent.voice_id or settings.retell_default_voice_id,
        )
    except Exception:
        logger.exception("Échec du provisionnement automatique de l'agent Retell pour l'agent %s", agent.id)


@router.post("/agents", response_model=AgentOut)
def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    agent = Agent(organization_id=organization_id, **payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)

    _provision_retell_agent_if_configured(agent)
    db.commit()
    db.refresh(agent)

    return agent


@router.get("/agents", response_model=list[AgentOut])
def list_agents(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return db.query(Agent).filter(Agent.organization_id == organization_id).all()


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

    updates = payload.model_dump(exclude_unset=True)
    needs_reprovision = any(field in updates for field in ("voice_id", "system_prompt", "language", "name"))

    for field, value in updates.items():
        setattr(agent, field, value)

    if needs_reprovision:
        _provision_retell_agent_if_configured(agent)

    db.commit()
    db.refresh(agent)
    return agent


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

    return WebCallOut(access_token=result["access_token"], call_id=result["call_id"])
