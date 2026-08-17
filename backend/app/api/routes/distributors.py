"""
Endpoints Distributeur (section 39 du cahier des charges).

Principe de granularité des accès (section 39.4) : un distributeur ne voit
que des données agrégées (nombre de clients, nombre d'appels, commissions) et
la liste de ses clients — jamais les transcripts, enregistrements ou contacts
détaillés de ces clients. Ces endpoints ne joignent donc jamais les tables
Call.transcript / Contact.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.distributor import Distributor
from app.models.organization import Organization
from app.models.call import Call
from app.models.commission import Commission

router = APIRouter()

# Placeholder MVP : en attendant le vrai moteur de billing (sections 20-21),
# on calcule un chiffre d'affaires simulé à partir d'un prix fixe par appel.
# À remplacer par la vraie consommation facturée du client une fois le moteur
# de billing branché.
MOCK_PRICE_PER_CALL_FCFA = 500.0


# ---------- Schémas ----------

class DistributorCreate(BaseModel):
    name: str
    email: EmailStr
    country: str | None = None
    commission_rate: float = 10.0


class DistributorOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    country: str | None
    commission_rate: float
    status: str

    class Config:
        from_attributes = True


class CommissionRateUpdate(BaseModel):
    commission_rate: float


class ClientCreate(BaseModel):
    name: str
    country: str | None = None


class ClientOut(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardOut(BaseModel):
    distributor: DistributorOut
    total_clients: int
    total_calls: int
    current_period: str
    estimated_commission_current_period: float


class CommissionOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    period: str
    base_amount: float
    rate_applied: float
    commission_amount: float
    status: str

    class Config:
        from_attributes = True


# ---------- Aide ----------

def get_distributor_or_404(distributor_id: uuid.UUID, db: Session) -> Distributor:
    distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributeur introuvable")
    return distributor


def current_period() -> str:
    return datetime.utcnow().strftime("%Y-%m")


# ---------- Endpoints ----------

@router.post("/distributors", response_model=DistributorOut)
def create_distributor(payload: DistributorCreate, db: Session = Depends(get_db)):
    """Création d'un distributeur — action Super Admin (section 22)."""
    existing = db.query(Distributor).filter(Distributor.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un distributeur avec cet email existe déjà")

    distributor = Distributor(**payload.model_dump())
    db.add(distributor)
    db.commit()
    db.refresh(distributor)
    return distributor


@router.get("/distributors", response_model=list[DistributorOut])
def list_distributors(db: Session = Depends(get_db)):
    """Vue Super Admin : liste de tous les distributeurs."""
    return db.query(Distributor).all()


@router.patch("/distributors/{distributor_id}/commission-rate", response_model=DistributorOut)
def update_commission_rate(
    distributor_id: uuid.UUID, payload: CommissionRateUpdate, db: Session = Depends(get_db)
):
    distributor = get_distributor_or_404(distributor_id, db)
    distributor.commission_rate = payload.commission_rate
    db.commit()
    db.refresh(distributor)
    return distributor


@router.get("/distributors/{distributor_id}/clients", response_model=list[ClientOut])
def list_distributor_clients(distributor_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Portefeuille de clients de ce distributeur uniquement — isolation stricte
    (section 3 et 39.2) : seules les organizations avec ce distributor_id.
    """
    get_distributor_or_404(distributor_id, db)
    return db.query(Organization).filter(Organization.distributor_id == distributor_id).all()


@router.post("/distributors/{distributor_id}/clients", response_model=ClientOut)
def onboard_client(distributor_id: uuid.UUID, payload: ClientCreate, db: Session = Depends(get_db)):
    """
    Onboarding : le distributeur crée un nouveau client, automatiquement
    rattaché à lui (section 39.3).
    """
    get_distributor_or_404(distributor_id, db)
    org = Organization(name=payload.name, country=payload.country, distributor_id=distributor_id)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/distributors/{distributor_id}/dashboard", response_model=DashboardOut)
def distributor_dashboard(distributor_id: uuid.UUID, db: Session = Depends(get_db)):
    distributor = get_distributor_or_404(distributor_id, db)

    client_ids = [
        row.id
        for row in db.query(Organization.id).filter(Organization.distributor_id == distributor_id).all()
    ]
    total_clients = len(client_ids)

    total_calls = 0
    if client_ids:
        total_calls = db.query(Call).filter(Call.organization_id.in_(client_ids)).count()

    base_amount = total_calls * MOCK_PRICE_PER_CALL_FCFA
    estimated_commission = base_amount * (distributor.commission_rate / 100)

    return DashboardOut(
        distributor=distributor,
        total_clients=total_clients,
        total_calls=total_calls,
        current_period=current_period(),
        estimated_commission_current_period=estimated_commission,
    )


@router.post("/distributors/{distributor_id}/commissions/calculate", response_model=list[CommissionOut])
def calculate_commissions(distributor_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Calcule et enregistre la commission du mois en cours, par client, pour ce
    distributeur (section 39.5). Idempotent : recalculer le même mois met à
    jour l'enregistrement existant plutôt que d'en créer un doublon.
    """
    distributor = get_distributor_or_404(distributor_id, db)
    period = current_period()

    clients = db.query(Organization).filter(Organization.distributor_id == distributor_id).all()

    results = []
    for client in clients:
        calls_count = db.query(Call).filter(Call.organization_id == client.id).count()
        base_amount = calls_count * MOCK_PRICE_PER_CALL_FCFA
        commission_amount = base_amount * (distributor.commission_rate / 100)

        existing = (
            db.query(Commission)
            .filter(
                Commission.distributor_id == distributor_id,
                Commission.organization_id == client.id,
                Commission.period == period,
            )
            .first()
        )
        if existing:
            existing.base_amount = base_amount
            existing.rate_applied = distributor.commission_rate
            existing.commission_amount = commission_amount
            record = existing
        else:
            record = Commission(
                distributor_id=distributor_id,
                organization_id=client.id,
                period=period,
                base_amount=base_amount,
                rate_applied=distributor.commission_rate,
                commission_amount=commission_amount,
                status="pending",
            )
            db.add(record)
        results.append(record)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


@router.get("/distributors/{distributor_id}/commissions", response_model=list[CommissionOut])
def list_commissions(distributor_id: uuid.UUID, db: Session = Depends(get_db)):
    get_distributor_or_404(distributor_id, db)
    return (
        db.query(Commission)
        .filter(Commission.distributor_id == distributor_id)
        .order_by(Commission.period.desc())
        .all()
    )
