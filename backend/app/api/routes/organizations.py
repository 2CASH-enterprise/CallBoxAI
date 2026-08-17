"""
Endpoints Organizations (entreprises clientes).
"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.organization import Organization

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
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    org = Organization(name=payload.name, country=payload.country)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(db: Session = Depends(get_db)):
    return db.query(Organization).all()
