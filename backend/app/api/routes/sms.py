"""
Consultation du journal des SMS (section 5/16 du cahier des charges).
En mode Mock, aucun SMS n'est réellement délivré — cette page sert de
preuve consultable, à la place d'une vraie livraison (équivalent de
Mailhog pour l'email, qui lui délivre réellement).
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.sms_log import SmsLog

router = APIRouter()


class SmsLogOut(BaseModel):
    id: uuid.UUID
    to_number: str
    body: str
    provider: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/sms", response_model=list[SmsLogOut])
def list_sms(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return (
        db.query(SmsLog)
        .filter(SmsLog.organization_id == organization_id)
        .order_by(SmsLog.created_at.desc())
        .all()
    )
