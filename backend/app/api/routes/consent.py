"""
Registre de consentement (section 42/43 du cahier des charges) — preuve
horodatée et immuable qu'un contact a accepté d'être appelé. Voir
app.models.consent_record pour le principe d'immuabilité.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.consent_record import ConsentRecord
from app.models.contact import Contact

router = APIRouter(prefix="/consent", tags=["consent"])


class ConsentCreate(BaseModel):
    contact_phone: str
    contact_name: str | None = None
    source: str
    campaign_reference: str | None = None
    consent_text: str


class ConsentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    contact_id: uuid.UUID
    source: str
    campaign_reference: str | None
    consent_text: str
    consented_at: datetime
    revoked_at: datetime | None

    class Config:
        from_attributes = True


@router.post("", response_model=ConsentOut)
def record_consent(
    payload: ConsentCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Enregistre un consentement — retrouve ou crée le contact par téléphone
    (même logique que les autres outils de la plateforme, section 18).
    N'écrase JAMAIS un consentement précédent : chaque appel à cet endpoint
    crée une nouvelle ligne, l'historique complet reste consultable.
    """
    contact = db.query(Contact).filter(
        Contact.organization_id == organization_id, Contact.phone == payload.contact_phone
    ).first()
    if not contact:
        contact = Contact(organization_id=organization_id, phone=payload.contact_phone, first_name=payload.contact_name)
        db.add(contact)
        db.flush()

    record = ConsentRecord(
        organization_id=organization_id,
        contact_id=contact.id,
        source=payload.source,
        campaign_reference=payload.campaign_reference,
        consent_text=payload.consent_text,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[ConsentOut])
def list_consent_records(
    contact_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """Historique complet — utile pour présenter une preuve en cas de contrôle."""
    query = db.query(ConsentRecord).filter(ConsentRecord.organization_id == organization_id)
    if contact_id:
        query = query.filter(ConsentRecord.contact_id == contact_id)
    return query.order_by(ConsentRecord.consented_at.desc()).all()


@router.post("/{consent_id}/revoke", response_model=ConsentOut)
def revoke_consent(
    consent_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Seule modification jamais autorisée sur un enregistrement de
    consentement : marquer son retrait, sans jamais toucher aux faits
    d'origine (texte, date, source).
    """
    record = db.query(ConsentRecord).filter(
        ConsentRecord.id == consent_id, ConsentRecord.organization_id == organization_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Enregistrement de consentement introuvable")
    if record.revoked_at is None:
        record.revoked_at = datetime.utcnow()
        db.commit()
        db.refresh(record)
    return record


def has_valid_consent(db: Session, organization_id: uuid.UUID, contact_id: uuid.UUID) -> bool:
    """
    Fonction réutilisable (section 42/43) : un contact a un consentement
    valide s'il existe AU MOINS UN enregistrement non révoqué — utilisée par
    le futur "Compliance Check" avant de déclencher un appel B2C.
    """
    return (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.organization_id == organization_id,
            ConsentRecord.contact_id == contact_id,
            ConsentRecord.revoked_at.is_(None),
        )
        .first()
        is not None
    )
