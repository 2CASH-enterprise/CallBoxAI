"""
Endpoints Contacts (CRM minimal — section 18 du cahier des charges).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.contacts_import import import_contacts_from_csv_text, ImportSummary
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


class ImportTextRequest(BaseModel):
    content: str


@router.post("/contacts", response_model=ContactOut)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
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
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return db.query(Contact).filter(Contact.organization_id == organization_id).all()


@router.post("/contacts/import/upload", response_model=ImportSummary)
async def import_contacts_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Import en masse par fichier CSV (colonnes phone/first_name/last_name).
    Pour importer 1000 contacts d'un coup plutôt qu'un par un (section 18).
    """
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    summary, _contacts = import_contacts_from_csv_text(db, organization_id, raw)
    db.commit()
    return summary


@router.post("/contacts/import/text", response_model=ImportSummary)
def import_contacts_text(
    payload: ImportTextRequest,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Import en masse par texte collé directement (même format CSV — au moins
    une colonne "phone"). Pratique pour coller une liste depuis Excel/Sheets
    sans avoir à d'abord l'exporter en fichier.
    """
    summary, _contacts = import_contacts_from_csv_text(db, organization_id, payload.content)
    db.commit()
    return summary
