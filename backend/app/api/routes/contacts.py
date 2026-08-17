"""
Endpoints Contacts (CRM minimal — section 18 du cahier des charges).
"""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact

router = APIRouter()

VALID_STATUSES = {
    "Nouveau", "Contacté", "Intéressé", "À rappeler",
    "RDV", "Pas intéressé", "Converti",
}


class ContactCreate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str
    status: str = "Nouveau"


class ContactOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    first_name: str | None
    last_name: str | None
    phone: str
    status: str

    class Config:
        from_attributes = True


def get_organization_id(x_organization_id: str = Header(...)) -> uuid.UUID:
    try:
        return uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="x-organization-id invalide")


@router.post("/contacts", response_model=ContactOut)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Statut invalide")
    contact = Contact(organization_id=organization_id, **payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/contacts", response_model=list[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
):
    return db.query(Contact).filter(Contact.organization_id == organization_id).all()
