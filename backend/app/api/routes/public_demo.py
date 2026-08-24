"""
Appel de démo public depuis la landing page (section 1 du cahier des
charges — vitrine commerciale). Contrairement à toutes les autres routes,
celle-ci n'est PAS protégée par organization_id/JWT : n'importe quel
visiteur du site peut la déclencher, sans compte. Elle déclenche un VRAI
appel téléphonique payant — d'où la limite anti-abus stricte (section 29).
"""
import logging
import re
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.demo_call_log import DemoCallLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["public"])

PHONE_REGEX = re.compile(r"^\+?[0-9]{8,15}$")
DAILY_LIMIT_PER_PHONE = 1


class DemoCallRequest(BaseModel):
    phone_number: str


class DemoCallResult(BaseModel):
    success: bool
    message: str


def _clean_phone(raw: str) -> str:
    return re.sub(r"[\s\-.()]", "", raw.strip())


@router.post("/demo-call", response_model=DemoCallResult)
def request_demo_call(payload: DemoCallRequest, db: Session = Depends(get_db)):
    phone = _clean_phone(payload.phone_number)
    if not PHONE_REGEX.match(phone):
        raise HTTPException(status_code=400, detail="Numéro de téléphone invalide (format international attendu).")

    since = datetime.utcnow() - timedelta(hours=24)
    recent_count = db.query(DemoCallLog).filter(
        DemoCallLog.phone_number == phone, DemoCallLog.created_at >= since
    ).count()
    if recent_count >= DAILY_LIMIT_PER_PHONE:
        raise HTTPException(
            status_code=429,
            detail="Ce numéro a déjà testé la démo aujourd'hui — réessayez demain, ou contactez-nous directement.",
        )

    if not settings.demo_agent_retell_id or not settings.demo_from_number:
        logger.warning("Appel de démo demandé mais DEMO_AGENT_RETELL_ID/DEMO_FROM_NUMBER non configurés")
        raise HTTPException(status_code=503, detail="La démo n'est pas disponible pour le moment, réessayez plus tard.")

    try:
        from app.providers.voice.retell_provider import RetellProvider

        provider = RetellProvider(api_key=settings.retell_api_key, agent_id=settings.demo_agent_retell_id)
        provider.create_phone_call(to_number=phone, from_number=settings.demo_from_number)
    except Exception:
        logger.exception("Échec du déclenchement de l'appel de démo pour %s", phone)
        raise HTTPException(status_code=502, detail="Échec du déclenchement de l'appel, réessayez dans un instant.")

    db.add(DemoCallLog(phone_number=phone))
    db.commit()

    return DemoCallResult(success=True, message="Vous allez recevoir un appel dans quelques instants !")
