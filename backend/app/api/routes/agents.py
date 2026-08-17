"""
Endpoints Agents IA — toujours filtrés par organization_id (isolation multi-tenant,
section 3 du cahier des charges).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.config import settings
from app.models.agent import Agent

router = APIRouter()


class AgentCreate(BaseModel):
    name: str
    objective: str | None = None
    language: str = "fr"
    system_prompt: str | None = None
    transfer_enabled: bool = False
    transfer_number: str | None = None
    transfer_instructions: str | None = None
    retell_agent_id: str | None = None


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

    class Config:
        from_attributes = True


class WebCallOut(BaseModel):
    access_token: str
    call_id: str


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
    return agent


@router.get("/agents", response_model=list[AgentOut])
def list_agents(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return db.query(Agent).filter(Agent.organization_id == organization_id).all()


@router.post("/agents/{agent_id}/test-call", response_model=WebCallOut)
def create_test_web_call(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Démarre une session de test vocal en direct (Web Call, section 16) pour
    cet agent, via le navigateur — sans passer par Twilio ni par un numéro
    de téléphone. Nécessite RETELL_API_KEY configuré ET un ID d'agent Retell
    (sur l'agent lui-même, ou à défaut RETELL_AGENT_ID globalement).
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
            detail="Aucun agent Retell associé : renseignez retell_agent_id sur cet agent (ou RETELL_AGENT_ID globalement).",
        )

    from app.providers.voice.retell_provider import RetellProvider

    provider = RetellProvider(api_key=settings.retell_api_key, agent_id=effective_retell_agent_id)
    result = provider.create_web_call(agent_id=effective_retell_agent_id)

    return WebCallOut(access_token=result["access_token"], call_id=result["call_id"])
