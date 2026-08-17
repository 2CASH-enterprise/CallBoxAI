"""
Endpoints Organizations (entreprises clientes).

La création "libre" d'une organisation se fait désormais via /auth/register
(inscription en libre-service, section 6.1). Ces endpoints restent pour la
supervision Super Admin (section 22).
"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_super_admin
from app.models.organization import Organization
from app.models.user import User

router = APIRouter()


class OrganizationCreate(BaseModel):
    name: str
    country: str | None = None


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None = None

    class Config:
        from_attributes = True


@router.post("/organizations", response_model=OrganizationOut)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    org = Organization(name=payload.name, country=payload.country)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)):
    return db.query(Organization).all()
