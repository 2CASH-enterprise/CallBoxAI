"""
Dashboard Super Admin (section 22 du cahier des charges).

Principe : n'afficher que des métriques réellement calculées depuis la base
de données. Les indicateurs business avancés (MRR, ARR, churn, ARPU) qui
nécessitent un vrai moteur de facturation (sections 20-21, pas encore
construit) ne sont pas affichés ici plutôt que d'être approximés ou inventés.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
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
