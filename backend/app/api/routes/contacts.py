"""
Endpoints Contacts (CRM minimal — section 18 du cahier des charges).
"""
import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Form
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
    company: str | None = None
    job_title: str | None = None
    source: str | None = None


class ContactUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    status: str | None = None
    company: str | None = None
    job_title: str | None = None
    source: str | None = None
    do_not_call: bool | None = None
    do_not_call_reason: str | None = None


class ContactOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    first_name: str | None
    last_name: str | None
    phone: str
    email: str | None
    status: str
    company: str | None = None
    job_title: str | None = None
    source: str | None = None
    do_not_call: bool = False
    do_not_call_reason: str | None = None

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


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Mise à jour manuelle d'un contact — sert notamment à marquer un contact
    en liste repoussoir (section 42/43) sans passer par un appel (ex. une
    demande reçue par email ou courrier), ou à corriger/compléter les
    champs enrichis B2B après import.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.organization_id == organization_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] is not None and updates["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Statut invalide")

    if updates.get("do_not_call") is True and not contact.do_not_call:
        updates["do_not_call_at"] = datetime.utcnow()
        if not updates.get("do_not_call_reason"):
            updates["do_not_call_reason"] = "Marqué manuellement par un utilisateur."

    for field, value in updates.items():
        setattr(contact, field, value)

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
    certify_consent: bool = Form(False),
    consent_note: str | None = Form(None),
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Import en masse par fichier CSV (colonnes phone/first_name/last_name).
    Pour importer 1000 contacts d'un coup plutôt qu'un par un (section 18).
    """
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    summary, _contacts = import_contacts_from_csv_text(
        db, organization_id, raw, certify_consent=certify_consent, consent_note=consent_note,
    )
    db.commit()
    return summary


class ImportTextRequestWithConsent(BaseModel):
    content: str
    certify_consent: bool = False
    consent_note: str | None = None


@router.post("/contacts/import/text", response_model=ImportSummary)
def import_contacts_text(
    payload: ImportTextRequestWithConsent,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Import en masse par texte collé directement (même format CSV — au moins
    une colonne "phone"). Pratique pour coller une liste depuis Excel/Sheets
    sans avoir à d'abord l'exporter en fichier.
    """
    summary, _contacts = import_contacts_from_csv_text(
        db, organization_id, payload.content,
        certify_consent=payload.certify_consent, consent_note=payload.consent_note,
    )
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


# ---------- Journal d'audit de conformité (section 42/43) ----------

class ComplianceAuditLogOut(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    campaign_id: uuid.UUID | None
    decision: str
    reason: str
    legal_basis: str | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/contacts/{contact_id}/compliance-log", response_model=list[ComplianceAuditLogOut])
def get_contact_compliance_log(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Historique complet des décisions de conformité pour ce contact (section
    42/43) — permet de reconstruire "pourquoi cet appel a été autorisé (ou
    bloqué)" en cas de contrôle.
    """
    from app.models.compliance_audit_log import ComplianceAuditLog

    logs = (
        db.query(ComplianceAuditLog)
        .filter(ComplianceAuditLog.contact_id == contact_id, ComplianceAuditLog.organization_id == organization_id)
        .order_by(ComplianceAuditLog.created_at.desc())
        .all()
    )
    return logs


# ---------- Droits RGPD génériques : accès et effacement (section 42/43) ----------
# Applicables à TOUTE la plateforme, quel que soit l'agent à l'origine du
# contact (accueil, service client, prospection...) — pas propres à la
# prospection commerciale.

class DataSubjectRequestOut(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    request_type: str
    status: str
    notes: str | None
    requested_at: datetime
    fulfilled_at: datetime | None

    class Config:
        from_attributes = True


class DataSubjectRequestCreate(BaseModel):
    request_type: str  # "access" | "erasure"
    notes: str | None = None


@router.post("/contacts/{contact_id}/data-subject-requests", response_model=DataSubjectRequestOut)
def create_data_subject_request(
    contact_id: uuid.UUID,
    payload: DataSubjectRequestCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """Enregistre une demande d'exercice de droit (accès ou effacement), avant de la traiter."""
    if payload.request_type not in ("access", "erasure"):
        raise HTTPException(status_code=400, detail="Type de demande invalide (attendu : access ou erasure)")

    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.organization_id == organization_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    from app.models.data_subject_request import DataSubjectRequest

    request = DataSubjectRequest(
        organization_id=organization_id, contact_id=contact_id,
        request_type=payload.request_type, notes=payload.notes,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/contacts/{contact_id}/data-subject-requests", response_model=list[DataSubjectRequestOut])
def list_data_subject_requests(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    from app.models.data_subject_request import DataSubjectRequest

    return (
        db.query(DataSubjectRequest)
        .filter(DataSubjectRequest.contact_id == contact_id, DataSubjectRequest.organization_id == organization_id)
        .order_by(DataSubjectRequest.requested_at.desc())
        .all()
    )


@router.get("/contacts/{contact_id}/data-export")
def export_contact_data(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Droit d'accès (section 42/43) : compile l'intégralité des données
    détenues sur ce contact — à remettre à la personne qui en fait la
    demande. Marque automatiquement la dernière demande d'accès en attente
    comme traitée, s'il en existe une.
    """
    from app.models.appointment import Appointment
    from app.models.ticket import Ticket
    from app.models.call import Call
    from app.models.consent_record import ConsentRecord
    from app.models.compliance_audit_log import ComplianceAuditLog
    from app.models.whatsapp_log import WhatsAppLog
    from app.models.sms_log import SmsLog
    from app.models.data_subject_request import DataSubjectRequest

    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.organization_id == organization_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    calls = db.query(Call).filter(Call.contact_id == contact_id, Call.organization_id == organization_id).all()
    appointments = db.query(Appointment).filter(Appointment.contact_id == contact_id, Appointment.organization_id == organization_id).all()
    tickets = db.query(Ticket).filter(Ticket.contact_id == contact_id, Ticket.organization_id == organization_id).all()
    consents = db.query(ConsentRecord).filter(ConsentRecord.contact_id == contact_id, ConsentRecord.organization_id == organization_id).all()
    audit_logs = db.query(ComplianceAuditLog).filter(ComplianceAuditLog.contact_id == contact_id, ComplianceAuditLog.organization_id == organization_id).all()
    whatsapp_logs = db.query(WhatsAppLog).filter(WhatsAppLog.to_number == contact.phone, WhatsAppLog.organization_id == organization_id).all()
    sms_logs = db.query(SmsLog).filter(SmsLog.to_number == contact.phone, SmsLog.organization_id == organization_id).all()

    export = {
        "contact": {
            "id": str(contact.id), "first_name": contact.first_name, "last_name": contact.last_name,
            "phone": contact.phone, "email": contact.email, "status": contact.status,
            "company": contact.company, "job_title": contact.job_title, "source": contact.source,
            "do_not_call": contact.do_not_call, "created_at": contact.created_at.isoformat(),
        },
        "calls": [
            {
                "id": str(c.id), "direction": c.direction, "status": c.status, "started_at": c.started_at.isoformat(),
                "duration_seconds": c.duration_seconds, "qualification": c.qualification, "intent": c.intent,
                "sentiment": c.sentiment, "transcript": c.transcript, "summary": c.summary,
            } for c in calls
        ],
        "appointments": [
            {"id": str(a.id), "scheduled_at": a.scheduled_at.isoformat(), "status": a.status, "notes": a.notes}
            for a in appointments
        ],
        "tickets": [
            {"id": str(t.id), "subject": t.subject, "status": t.status, "created_at": t.created_at.isoformat()}
            for t in tickets
        ],
        "consent_records": [
            {"id": str(c.id), "source": c.source, "consent_text": c.consent_text, "consented_at": c.consented_at.isoformat(), "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None}
            for c in consents
        ],
        "compliance_audit_logs": [
            {"decision": a.decision, "reason": a.reason, "legal_basis": a.legal_basis, "created_at": a.created_at.isoformat()}
            for a in audit_logs
        ],
        "whatsapp_messages": [{"body": w.body, "created_at": w.created_at.isoformat()} for w in whatsapp_logs],
        "sms_messages": [{"body": s.body, "created_at": s.created_at.isoformat()} for s in sms_logs],
    }

    pending_access_request = (
        db.query(DataSubjectRequest)
        .filter(
            DataSubjectRequest.contact_id == contact_id, DataSubjectRequest.organization_id == organization_id,
            DataSubjectRequest.request_type == "access", DataSubjectRequest.status == "pending",
        )
        .first()
    )
    if pending_access_request:
        pending_access_request.status = "fulfilled"
        pending_access_request.fulfilled_at = datetime.utcnow()
        db.commit()

    return export


@router.post("/contacts/{contact_id}/erase")
def erase_contact_data(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Droit à l'effacement (section 42/43) : anonymise l'identité du contact
    (nom, email, entreprise) et le contenu détaillé de ses appels — mais
    conserve le NUMÉRO en liste repoussoir définitive, pour empêcher qu'il
    soit réimporté et rappelé par erreur plus tard, ce qui irait à
    l'encontre même de la demande d'effacement.
    """
    from app.models.call import Call
    from app.models.data_subject_request import DataSubjectRequest

    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.organization_id == organization_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    ERASURE_PLACEHOLDER = "[Effacé à la demande de la personne concernée]"

    contact.first_name = None
    contact.last_name = None
    contact.email = None
    contact.company = None
    contact.job_title = None
    contact.source = None
    contact.do_not_call = True
    contact.do_not_call_reason = "Effacement RGPD — ne jamais réimporter ni rappeler ce numéro."
    contact.do_not_call_at = datetime.utcnow()

    calls = db.query(Call).filter(Call.contact_id == contact_id, Call.organization_id == organization_id).all()
    for call in calls:
        if call.transcript:
            call.transcript = ERASURE_PLACEHOLDER
        if call.summary:
            call.summary = ERASURE_PLACEHOLDER

    pending_erasure_request = (
        db.query(DataSubjectRequest)
        .filter(
            DataSubjectRequest.contact_id == contact_id, DataSubjectRequest.organization_id == organization_id,
            DataSubjectRequest.request_type == "erasure", DataSubjectRequest.status == "pending",
        )
        .first()
    )
    if pending_erasure_request:
        pending_erasure_request.status = "fulfilled"
        pending_erasure_request.fulfilled_at = datetime.utcnow()
    else:
        db.add(DataSubjectRequest(
            organization_id=organization_id, contact_id=contact_id, request_type="erasure",
            status="fulfilled", fulfilled_at=datetime.utcnow(),
            notes="Effacement déclenché directement, sans demande préalablement enregistrée.",
        ))

    db.commit()
    return {"status": "erased", "contact_id": str(contact_id), "calls_redacted": len(calls)}
