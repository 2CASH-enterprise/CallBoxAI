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
from datetime import datetime

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db
from app.models.call import Call
from app.models.agent import Agent
from app.models.contact import Contact

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _get_or_create_call(db: Session, call_data: dict, provider_call_id: str) -> Call | None:
    """
    Retrouve l'appel correspondant, ou le CRÉE à la volée si c'est un
    véritable appel entrant que nous n'avons pas nous-mêmes déclenché
    (section 16/30) — contrairement à "Simuler un appel" ou "Tester en
    direct", qui créent déjà cette ligne à l'avance, un vrai appel entrant
    sur un numéro connecté n'a AUCUNE ligne existante avant ce webhook.

    Le contact appelant est retrouvé (ou créé) par téléphone — même logique
    de réutilisation que l'import CSV et les outils PMS en direct.
    """
    call = db.query(Call).filter(Call.provider_call_id == provider_call_id).first()
    if call:
        return call

    retell_agent_id = call_data.get("agent_id")
    if not retell_agent_id:
        return None

    agent = db.query(Agent).filter(Agent.retell_agent_id == retell_agent_id).first()
    if not agent:
        return None

    direction = call_data.get("direction", "inbound")
    caller_phone = call_data.get("from_number") if direction == "inbound" else call_data.get("to_number")

    contact_id = None
    if caller_phone:
        contact = db.query(Contact).filter(
            Contact.organization_id == agent.organization_id, Contact.phone == caller_phone
        ).first()
        if not contact:
            contact = Contact(organization_id=agent.organization_id, phone=caller_phone)
            db.add(contact)
            db.flush()
        contact_id = contact.id

    call = Call(
        organization_id=agent.organization_id,
        agent_id=agent.id,
        contact_id=contact_id,
        direction=direction,
        status="in_progress",
        provider="retell",
        provider_call_id=provider_call_id,
        started_at=datetime.utcnow(),
    )
    db.add(call)
    db.flush()
    return call


@router.post("/retell")
async def retell_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Reçoit les événements de fin d'appel envoyés par Retell (call_ended,
    call_analyzed) et complète l'enregistrement Call correspondant — le
    créant d'abord si besoin (voir _get_or_create_call) — y compris la
    classification, le ticket de service client et la mise à jour du CRM
    (section 16/19/30), exactement comme pour un appel simulé (voir
    app.core.call_pipeline.apply_post_call_analytics).

    TODO avant production : vérifier l'en-tête X-Retell-Signature (HMAC avec
    la clé secrète du compte) pour s'assurer que la requête vient bien de
    Retell et n'a pas été forgée — voir la documentation Retell sur la
    vérification de signature des webhooks.
    """
    payload = await request.json()
    call_data = payload.get("call", {})
    provider_call_id = call_data.get("call_id")

    logger.info(
        "Webhook Retell reçu : event=%s call_id=%s agent_id=%s direction=%s from=%s",
        payload.get("event"), provider_call_id, call_data.get("agent_id"),
        call_data.get("direction"), call_data.get("from_number"),
    )

    if not provider_call_id:
        logger.warning("Webhook Retell ignoré : call_id manquant dans le payload")
        return {"status": "ignored", "reason": "call_id manquant"}

    call = _get_or_create_call(db, call_data, provider_call_id)
    if not call:
        logger.warning(
            "Webhook Retell ignoré : agent_id=%s introuvable parmi les agents CallBoxAI "
            "(webhook_url probablement configuré sur un agent Retell orphelin/dupliqué, "
            "ou provisionné avant la correction du webhook_url)",
            call_data.get("agent_id"),
        )
        return {"status": "ignored", "reason": "appel inconnu (agent Retell non reconnu)"}

    if "transcript" in call_data:
        call.transcript = call_data["transcript"]
    analysis = call_data.get("call_analysis") or {}
    if "call_summary" in analysis:
        call.summary = analysis["call_summary"]

    event = payload.get("event")
    if event == "call_ended" and call.status == "in_progress":
        call.status = "completed"

    # call_analyzed arrive en dernier (après call_ended), une fois le
    # résumé/transcript final disponibles — c'est le bon moment pour
    # classifier. Garde d'idempotence sur `call.intent is None` : Retell
    # peut retenter la livraison du webhook plusieurs fois (section 29).
    if event == "call_analyzed" and call.intent is None:
        agent = db.query(Agent).filter(Agent.id == call.agent_id).first()
        if agent:
            from app.core.call_pipeline import apply_post_call_analytics
            # KeywordAnalyticsProvider (pas Mock) : ici, on traite un VRAI
            # appel avec un VRAI transcript — l'analyse doit porter sur ce
            # qui a réellement été dit, pas un tirage au sort (section 19).
            from app.providers.analytics.keyword import KeywordAnalyticsProvider

            apply_post_call_analytics(db, call.organization_id, agent, call, KeywordAnalyticsProvider(), call.contact_id)
        if call.status == "in_progress":
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
