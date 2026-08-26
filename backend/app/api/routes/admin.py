"""
Dashboard Super Admin (section 22 du cahier des charges).

Principe : n'afficher que des métriques réellement calculées depuis la base
de données. Les indicateurs business avancés (MRR, ARR, churn, ARPU) qui
nécessitent un vrai moteur de facturation (sections 20-21, pas encore
construit) ne sont pas affichés ici plutôt que d'être approximés ou inventés.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_super_admin
from app.core.pricing import MOCK_PRICE_PER_CALL_FCFA
from app.models.organization import Organization
from app.models.distributor import Distributor
from app.models.agent import Agent
from app.models.call import Call
from app.models.user import User
from app.models.agent_request import AgentRequest, VALID_STATUSES as AGENT_REQUEST_STATUSES
from app.api.routes.agents import AgentCreate

router = APIRouter(prefix="/admin", tags=["admin"])


class TotalsOut(BaseModel):
    organizations: int
    organizations_direct: int
    organizations_via_distributor: int
    distributors: int
    agents: int
    calls_total: int
    calls_today: int
    users: int


class OrganizationSummaryOut(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    distributor_name: str | None
    agents_count: int
    calls_count: int
    created_at: datetime


class DistributorSummaryOut(BaseModel):
    id: uuid.UUID
    name: str
    commission_rate: float
    clients_count: int
    calls_count: int


class AdminDashboardOut(BaseModel):
    totals: TotalsOut
    current_period: str
    estimated_revenue_current_period: float
    estimated_commissions_current_period: float
    organizations: list[OrganizationSummaryOut]
    distributors: list[DistributorSummaryOut]


@router.get("/dashboard", response_model=AdminDashboardOut)
def admin_dashboard(db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)):
    total_orgs = db.query(Organization).count()
    orgs_via_distributor = db.query(Organization).filter(Organization.distributor_id.isnot(None)).count()
    orgs_direct = total_orgs - orgs_via_distributor
    total_distributors = db.query(Distributor).count()
    total_agents = db.query(Agent).count()
    total_calls = db.query(Call).count()
    total_users = db.query(User).count()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    calls_today = db.query(Call).filter(Call.started_at >= today_start).count()

    estimated_revenue = total_calls * MOCK_PRICE_PER_CALL_FCFA
    period = datetime.utcnow().strftime("%Y-%m")

    all_distributors = db.query(Distributor).all()
    distributor_names = {d.id: d.name for d in all_distributors}

    total_commissions = 0.0
    distributor_rows = []
    for d in all_distributors:
        client_ids = [
            row.id for row in db.query(Organization.id).filter(Organization.distributor_id == d.id).all()
        ]
        clients_count = len(client_ids)
        calls_count = db.query(Call).filter(Call.organization_id.in_(client_ids)).count() if client_ids else 0
        commission = calls_count * MOCK_PRICE_PER_CALL_FCFA * (d.commission_rate / 100)
        total_commissions += commission
        distributor_rows.append(
            DistributorSummaryOut(
                id=d.id,
                name=d.name,
                commission_rate=d.commission_rate,
                clients_count=clients_count,
                calls_count=calls_count,
            )
        )

    recent_orgs = db.query(Organization).order_by(Organization.created_at.desc()).limit(20).all()
    organization_rows = []
    for o in recent_orgs:
        agents_count = db.query(Agent).filter(Agent.organization_id == o.id).count()
        calls_count = db.query(Call).filter(Call.organization_id == o.id).count()
        organization_rows.append(
            OrganizationSummaryOut(
                id=o.id,
                name=o.name,
                country=o.country,
                distributor_name=distributor_names.get(o.distributor_id),
                agents_count=agents_count,
                calls_count=calls_count,
                created_at=o.created_at,
            )
        )

    return AdminDashboardOut(
        totals=TotalsOut(
            organizations=total_orgs,
            organizations_direct=orgs_direct,
            organizations_via_distributor=orgs_via_distributor,
            distributors=total_distributors,
            agents=total_agents,
            calls_total=total_calls,
            calls_today=calls_today,
            users=total_users,
        ),
        current_period=period,
        estimated_revenue_current_period=estimated_revenue,
        estimated_commissions_current_period=total_commissions,
        organizations=organization_rows,
        distributors=distributor_rows,
    )


# ---------- Demandes de création d'agent (section 41) ----------
# Le Super Admin configure et crée l'agent pour le compte du client, à
# partir de sa demande — voir app.api.routes.agents pour le côté client.

class AgentRequestOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    use_case: str
    objective: str
    status: str
    admin_notes: str | None
    created_agent_id: uuid.UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentRequestStatusUpdate(BaseModel):
    status: str
    admin_notes: str | None = None


@router.get("/agent-requests", response_model=list[AgentRequestOut])
def list_all_agent_requests(
    status: str | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """Toutes les demandes, toutes organisations confondues — filtrable par statut."""
    query = db.query(AgentRequest, Organization).join(Organization, AgentRequest.organization_id == Organization.id)
    if status:
        query = query.filter(AgentRequest.status == status)
    rows = query.order_by(AgentRequest.created_at.desc()).all()
    return [
        AgentRequestOut(
            id=r.id, organization_id=r.organization_id, organization_name=org.name,
            use_case=r.use_case, objective=r.objective, status=r.status,
            admin_notes=r.admin_notes, created_agent_id=r.created_agent_id, created_at=r.created_at,
        )
        for r, org in rows
    ]


@router.patch("/agent-requests/{request_id}", response_model=AgentRequestOut)
def update_agent_request_status(
    request_id: uuid.UUID,
    payload: AgentRequestStatusUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """Change le statut sans créer d'agent (ex. 'in_progress', ou 'rejected' avec un motif)."""
    request = db.query(AgentRequest).filter(AgentRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    if payload.status not in AGENT_REQUEST_STATUSES:
        raise HTTPException(status_code=400, detail="Statut invalide")

    request.status = payload.status
    if payload.admin_notes is not None:
        request.admin_notes = payload.admin_notes
    db.commit()
    db.refresh(request)

    org = db.query(Organization).filter(Organization.id == request.organization_id).first()
    return AgentRequestOut(
        id=request.id, organization_id=request.organization_id, organization_name=org.name if org else "?",
        use_case=request.use_case, objective=request.objective, status=request.status,
        admin_notes=request.admin_notes, created_agent_id=request.created_agent_id, created_at=request.created_at,
    )


@router.post("/agent-requests/{request_id}/fulfill", response_model=AgentRequestOut)
def fulfill_agent_request(
    request_id: uuid.UUID,
    payload: AgentCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """
    Crée réellement l'agent, configuré par le Super Admin, pour le compte
    de l'organisation à l'origine de la demande — clôt la demande.
    """
    from app.api.routes.agents import _create_agent_for_organization

    request = db.query(AgentRequest).filter(AgentRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    if request.status == "completed":
        raise HTTPException(status_code=400, detail="Cette demande a déjà été traitée")

    agent = _create_agent_for_organization(db, request.organization_id, payload)

    request.status = "completed"
    request.created_agent_id = agent.id
    db.commit()
    db.refresh(request)

    org = db.query(Organization).filter(Organization.id == request.organization_id).first()
    return AgentRequestOut(
        id=request.id, organization_id=request.organization_id, organization_name=org.name if org else "?",
        use_case=request.use_case, objective=request.objective, status=request.status,
        admin_notes=request.admin_notes, created_agent_id=request.created_agent_id, created_at=request.created_at,
    )
