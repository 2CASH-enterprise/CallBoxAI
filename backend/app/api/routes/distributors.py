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
from app.core.security import require_super_admin, require_distributor_access, hash_password
from app.models.distributor import Distributor
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.call import Call
from app.models.commission import Commission
from app.models.user import User
from app.core.pricing import MOCK_PRICE_PER_CALL_FCFA

router = APIRouter()

# Voir app.core.pricing pour le détail de ce placeholder MVP.


# ---------- Schémas ----------

class DistributorCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    country: str | None = None
    commission_rate: float = 10.0


class DistributorOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    country: str | None
    commission_rate: float
    status: str
    brand_name: str | None
    logo_url: str | None
    primary_color: str | None

    class Config:
        from_attributes = True


class BrandingUpdate(BaseModel):
    brand_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None


class CommissionRateUpdate(BaseModel):
    commission_rate: float


class ClientCreate(BaseModel):
    name: str
    country: str | None = None
    owner_email: EmailStr
    owner_password: str
    owner_full_name: str


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
def create_distributor(
    payload: DistributorCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """
    Création d'un distributeur — réservée au Super Admin (section 22).
    Crée dans la foulée le compte de connexion (login) du distributeur,
    pour qu'il puisse accéder à son propre Dashboard (section 39).
    """
    if db.query(Distributor).filter(Distributor.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Un distributeur avec cet email existe déjà")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Un compte utilisateur existe déjà avec cet email")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractères")

    distributor = Distributor(
        name=payload.name,
        email=payload.email,
        country=payload.country,
        commission_rate=payload.commission_rate,
    )
    db.add(distributor)
    db.flush()

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.name,
        distributor_id=distributor.id,
    )
    db.add(user)

    db.commit()
    db.refresh(distributor)
    return distributor


@router.get("/distributors", response_model=list[DistributorOut])
def list_distributors(db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)):
    """Vue Super Admin : liste de tous les distributeurs."""
    return db.query(Distributor).all()


@router.patch("/distributors/{distributor_id}/commission-rate", response_model=DistributorOut)
def update_commission_rate(
    distributor_id: uuid.UUID,
    payload: CommissionRateUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    distributor = get_distributor_or_404(distributor_id, db)
    distributor.commission_rate = payload.commission_rate
    db.commit()
    db.refresh(distributor)
    return distributor


@router.patch("/distributors/{distributor_id}/branding", response_model=DistributorOut)
def update_branding(
    distributor_id: uuid.UUID,
    payload: BrandingUpdate,
    db: Session = Depends(get_db),
    _access: uuid.UUID = Depends(require_distributor_access),
):
    """
    Marque blanche (white-label) : le distributeur définit son logo et son
    nom de marque, propagés à ses propres clients (voir /auth/me). Accessible
    au Super Admin ou au distributeur concerné lui-même (auto-service).
    """
    distributor = get_distributor_or_404(distributor_id, db)
    if payload.brand_name is not None:
        distributor.brand_name = payload.brand_name
    if payload.logo_url is not None:
        distributor.logo_url = payload.logo_url
    if payload.primary_color is not None:
        distributor.primary_color = payload.primary_color
    db.commit()
    db.refresh(distributor)
    return distributor


@router.get("/distributors/{distributor_id}/clients", response_model=list[ClientOut])
def list_distributor_clients(
    distributor_id: uuid.UUID,
    db: Session = Depends(get_db),
    _access: uuid.UUID = Depends(require_distributor_access),
):
    """
    Portefeuille de clients de ce distributeur uniquement — isolation stricte
    (section 3 et 39.2) : seules les organizations avec ce distributor_id.
    """
    get_distributor_or_404(distributor_id, db)
    return db.query(Organization).filter(Organization.distributor_id == distributor_id).all()


@router.post("/distributors/{distributor_id}/clients", response_model=ClientOut)
def onboard_client(
    distributor_id: uuid.UUID,
    payload: ClientCreate,
    db: Session = Depends(get_db),
    _access: uuid.UUID = Depends(require_distributor_access),
):
    """
    Onboarding : le distributeur crée un nouveau client, automatiquement
    rattaché à lui (section 39.3), ET crée dans la foulée le compte de
    connexion "Owner" de ce client — sans ça, le client ne pourrait jamais se
    connecter à son propre Dashboard.
    """
    get_distributor_or_404(distributor_id, db)

    if db.query(User).filter(User.email == payload.owner_email).first():
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email")
    if len(payload.owner_password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractères")

    org = Organization(name=payload.name, country=payload.country, distributor_id=distributor_id)
    db.add(org)
    db.flush()

    owner = User(
        email=payload.owner_email,
        password_hash=hash_password(payload.owner_password),
        full_name=payload.owner_full_name,
    )
    db.add(owner)
    db.flush()

    db.add(OrganizationMembership(user_id=owner.id, organization_id=org.id, role="owner"))
    db.commit()
    db.refresh(org)
    return org


@router.get("/distributors/{distributor_id}/dashboard", response_model=DashboardOut)
def distributor_dashboard(
    distributor_id: uuid.UUID,
    db: Session = Depends(get_db),
    _access: uuid.UUID = Depends(require_distributor_access),
):
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
def calculate_commissions(
    distributor_id: uuid.UUID,
    db: Session = Depends(get_db),
    _access: uuid.UUID = Depends(require_distributor_access),
):
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
def list_commissions(
    distributor_id: uuid.UUID,
    db: Session = Depends(get_db),
    _access: uuid.UUID = Depends(require_distributor_access),
):
    get_distributor_or_404(distributor_id, db)
    return (
        db.query(Commission)
        .filter(Commission.distributor_id == distributor_id)
        .order_by(Commission.period.desc())
        .all()
    )
