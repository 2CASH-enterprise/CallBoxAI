"""
Webhooks Retell/Twilio (section 30 du cahier des charges).

Contrairement aux autres routes, ces endpoints ne sont PAS protégés par JWT :
ce sont Retell/Twilio qui nous appellent, pas un utilisateur connecté. Leur
authenticité doit être vérifiée autrement (signature Retell, validation de
requête Twilio) — voir les TODO ci-dessous, à compléter avant la mise en
production réelle avec de vrais comptes (section 24 : ne jamais faire
confiance à une donnée non vérifiée).

Ces endpoints ne sont utiles qu'une fois VOICE_PROVIDER=retell et/ou
TELEPHONY_PROVIDER=twilio réellement activés (app.core.providers) — tant
qu'on reste en mode Mock, aucun vrai webhook n'arrive jamais ici.
"""
import uuid

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db
from app.models.call import Call

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/retell")
async def retell_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Reçoit les événements de fin d'appel envoyés par Retell (call_ended,
    call_analyzed) et complète l'enregistrement Call correspondant.

    TODO avant production : vérifier l'en-tête X-Retell-Signature (HMAC avec
    la clé secrète du compte) pour s'assurer que la requête vient bien de
    Retell et n'a pas été forgée — voir la documentation Retell sur la
    vérification de signature des webhooks.
    """
    payload = await request.json()
    call_data = payload.get("call", {})
    provider_call_id = call_data.get("call_id")

    if not provider_call_id:
        return {"status": "ignored", "reason": "call_id manquant"}

    call = db.query(Call).filter(Call.provider_call_id == provider_call_id).first()
    if not call:
        return {"status": "ignored", "reason": "appel inconnu"}

    if "transcript" in call_data:
        call.transcript = call_data["transcript"]
    analysis = call_data.get("call_analysis") or {}
    if "call_summary" in analysis:
        call.summary = analysis["call_summary"]

    if payload.get("event") == "call_ended":
        call.status = "completed"

    db.commit()
    return {"status": "ok"}


@router.post("/twilio")
async def twilio_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Reçoit les callbacks de statut d'appel envoyés par Twilio
    (application/x-www-form-urlencoded : CallSid, CallStatus, etc.).

    TODO avant production : valider la requête avec la signature Twilio
    (en-tête X-Twilio-Signature + TWILIO_AUTH_TOKEN, via
    twilio.request_validator.RequestValidator) pour rejeter toute requête
    qui ne vient pas réellement de Twilio.
    """
    form = await request.form()
    provider_call_id = form.get("CallSid")
    call_status = form.get("CallStatus")

    if not provider_call_id:
        return {"status": "ignored", "reason": "CallSid manquant"}

    call = db.query(Call).filter(Call.provider_call_id == provider_call_id).first()
    if not call:
        return {"status": "ignored", "reason": "appel inconnu"}

    status_map = {
        "completed": "completed",
        "busy": "failed",
        "no-answer": "failed",
        "failed": "failed",
        "canceled": "failed",
    }
    if call_status in status_map:
        call.status = status_map[call_status]

    db.commit()
    return {"status": "ok"}
