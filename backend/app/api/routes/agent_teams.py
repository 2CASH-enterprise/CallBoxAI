"""
Équipes d'agents (section 40 — palier "Growth", "Employé IA") : le client
compose librement un regroupement de ses agents déjà créés, sous un nom
personnalisé, pour obtenir une présentation combinée plutôt que des vues
séparées agent par agent.
"""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.agent_team import AgentTeam
from app.models.agent import Agent
from app.models.call import Call
from app.models.whatsapp_log import WhatsAppLog
from app.models.appointment import Appointment

router = APIRouter(prefix="/agent-teams", tags=["agent-teams"])


class AgentTeamCreate(BaseModel):
    name: str


class AgentTeamUpdate(BaseModel):
    name: str | None = None


class AgentTeamOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    agent_ids: list[uuid.UUID]
    created_at: datetime

    class Config:
        from_attributes = True


def _team_out(db: Session, team: AgentTeam) -> AgentTeamOut:
    agent_ids = [a.id for a in db.query(Agent.id).filter(Agent.team_id == team.id).all()]
    return AgentTeamOut(
        id=team.id, organization_id=team.organization_id, name=team.name,
        agent_ids=agent_ids, created_at=team.created_at,
    )


@router.post("", response_model=AgentTeamOut)
def create_team(
    payload: AgentTeamCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    team = AgentTeam(organization_id=organization_id, name=payload.name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return _team_out(db, team)


@router.get("", response_model=list[AgentTeamOut])
def list_teams(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    teams = db.query(AgentTeam).filter(AgentTeam.organization_id == organization_id).all()
    return [_team_out(db, t) for t in teams]


@router.patch("/{team_id}", response_model=AgentTeamOut)
def update_team(
    team_id: uuid.UUID,
    payload: AgentTeamUpdate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    team = db.query(AgentTeam).filter(AgentTeam.id == team_id, AgentTeam.organization_id == organization_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Équipe introuvable pour cette organisation")
    if payload.name is not None:
        team.name = payload.name
    db.commit()
    db.refresh(team)
    return _team_out(db, team)


@router.delete("/{team_id}")
def delete_team(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """Dissout l'équipe — les agents ne sont jamais supprimés, juste détachés du regroupement."""
    team = db.query(AgentTeam).filter(AgentTeam.id == team_id, AgentTeam.organization_id == organization_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Équipe introuvable pour cette organisation")
    db.query(Agent).filter(Agent.team_id == team_id).update({"team_id": None})
    db.delete(team)
    db.commit()
    return {"status": "ok"}


class TeamMemberUpdate(BaseModel):
    agent_id: uuid.UUID


@router.post("/{team_id}/agents", response_model=AgentTeamOut)
def add_agent_to_team(
    team_id: uuid.UUID,
    payload: TeamMemberUpdate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    team = db.query(AgentTeam).filter(AgentTeam.id == team_id, AgentTeam.organization_id == organization_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Équipe introuvable pour cette organisation")
    agent = db.query(Agent).filter(Agent.id == payload.agent_id, Agent.organization_id == organization_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable pour cette organisation")

    agent.team_id = team.id
    db.commit()
    return _team_out(db, team)


@router.delete("/{team_id}/agents/{agent_id}", response_model=AgentTeamOut)
def remove_agent_from_team(
    team_id: uuid.UUID,
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    team = db.query(AgentTeam).filter(AgentTeam.id == team_id, AgentTeam.organization_id == organization_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Équipe introuvable pour cette organisation")
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.organization_id == organization_id, Agent.team_id == team_id).first()
    if agent:
        agent.team_id = None
        db.commit()
    return _team_out(db, team)


# ---------- Résumé combiné (section 40) ----------

class TeamSummaryOut(BaseModel):
    team_id: uuid.UUID
    team_name: str
    since: datetime
    total_calls: int
    total_call_minutes: int
    total_whatsapp_messages: int
    total_appointments: int


@router.get("/{team_id}/summary", response_model=TeamSummaryOut)
def get_team_summary(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Résumé combiné de l'équipe sur les 30 derniers jours — UN chiffre par
    indicateur, peu importe lequel des agents de l'équipe l'a produit
    (section 40) : c'est ce qui distingue une vraie "équipe" d'une simple
    juxtaposition de plusieurs agents individuels.
    """
    team = db.query(AgentTeam).filter(AgentTeam.id == team_id, AgentTeam.organization_id == organization_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Équipe introuvable pour cette organisation")

    agent_ids = [a.id for a in db.query(Agent.id).filter(Agent.team_id == team_id).all()]
    since = datetime.utcnow() - timedelta(days=30)

    if not agent_ids:
        return TeamSummaryOut(
            team_id=team_id, team_name=team.name, since=since,
            total_calls=0, total_call_minutes=0, total_whatsapp_messages=0, total_appointments=0,
        )

    calls = db.query(Call).filter(Call.agent_id.in_(agent_ids), Call.started_at >= since).all()
    total_calls = len(calls)
    total_call_minutes = round(sum(c.duration_seconds or 0 for c in calls) / 60)

    total_whatsapp_messages = (
        db.query(WhatsAppLog)
        .filter(WhatsAppLog.agent_id.in_(agent_ids), WhatsAppLog.created_at >= since)
        .count()
    )
    total_appointments = (
        db.query(Appointment)
        .filter(Appointment.agent_id.in_(agent_ids), Appointment.created_at >= since, Appointment.status != "cancelled")
        .count()
    )

    return TeamSummaryOut(
        team_id=team_id, team_name=team.name, since=since,
        total_calls=total_calls, total_call_minutes=total_call_minutes,
        total_whatsapp_messages=total_whatsapp_messages, total_appointments=total_appointments,
    )
