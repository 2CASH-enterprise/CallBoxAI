"""
Endpoints Agents IA — toujours filtrés par organization_id (isolation multi-tenant,
section 3 du cahier des charges).
"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
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


class AgentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    objective: str | None = None
    language: str
    transfer_enabled: bool
    transfer_number: str | None
    transfer_instructions: str | None

    class Config:
        from_attributes = True


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
