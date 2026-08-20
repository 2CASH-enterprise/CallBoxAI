"""
Endpoints Contacts (CRM minimal — section 18 du cahier des charges).
"""
import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.contacts_import import import_contacts_from_csv_text, ImportSummary
from app.models.contact import Contact
from app.models.call import Call

router = APIRouter()

VALID_STATUSES = {
    "Nouveau", "Contacté", "Intéressé", "À rappeler",
    "RDV", "Pas intéressé", "Converti",
}

# Ordre de progression du pipeline de qualification (section 18/19). "À
# rappeler" et "Pas intéressé" sont des bifurcations, pas des étapes
# d'avancement — traités à part dans /contacts/pipeline.
FUNNEL_STAGES = ["Nouveau", "Contacté", "Intéressé", "RDV", "Converti"]
SIDE_BUCKETS = ["À rappeler", "Pas intéressé"]


class ContactCreate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str
    email: str | None = None
    status: str = "Nouveau"


class ContactOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    first_name: str | None
    last_name: str | None
    phone: str
    email: str | None
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


class PipelineStage(BaseModel):
    status: str
    count: int


class PipelineOut(BaseModel):
    funnel: list[PipelineStage]
    side_buckets: list[PipelineStage]
    total_contacts: int


@router.get("/contacts/pipeline", response_model=PipelineOut)
def get_pipeline(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Entonnoir de qualification (section 18/19) : où en sont les contacts
    dans leur progression Nouveau -> Contacté -> Intéressé -> RDV -> Converti,
    avec les bifurcations "À rappeler" et "Pas intéressé" à part.
    """
    contacts = db.query(Contact).filter(Contact.organization_id == organization_id).all()
    counts: dict[str, int] = {}
    for c in contacts:
        counts[c.status] = counts.get(c.status, 0) + 1

    return PipelineOut(
        funnel=[PipelineStage(status=s, count=counts.get(s, 0)) for s in FUNNEL_STAGES],
        side_buckets=[PipelineStage(status=s, count=counts.get(s, 0)) for s in SIDE_BUCKETS],
        total_contacts=len(contacts),
    )


@router.get("/contacts/export")
def export_contacts(
    status: str | None = None,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Export CSV des contacts (section 19 — leads qualifiés), enrichi avec la
    qualification du dernier appel connu pour chaque contact (intent, score,
    sentiment) — pas seulement les champs bruts du CRM. `status` permet de
    filtrer (ex. "Intéressé" pour n'exporter que les leads chauds/tièdes).
    """
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Statut invalide")

    query = db.query(Contact).filter(Contact.organization_id == organization_id)
    if status:
        query = query.filter(Contact.status == status)
    contacts = query.all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["phone", "first_name", "last_name", "email", "status", "last_call_qualification", "last_call_score", "last_call_intent", "last_call_date"])

    for contact in contacts:
        last_call = (
            db.query(Call)
            .filter(Call.contact_id == contact.id)
            .order_by(Call.started_at.desc())
            .first()
        )
        writer.writerow([
            contact.phone,
            contact.first_name or "",
            contact.last_name or "",
            contact.email or "",
            contact.status,
            last_call.qualification if last_call else "",
            last_call.score if last_call else "",
            last_call.intent if last_call else "",
            last_call.started_at.isoformat() if last_call else "",
        ])

    import unicodedata

    def slugify(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        return normalized.lower().replace(" ", "_")

    filename = f"leads_{slugify(status)}.csv" if status else "leads.csv"
    return Response(
        content=buffer.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
