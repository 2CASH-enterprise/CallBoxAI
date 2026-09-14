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
        # Durée réelle de l'appel (section 40 — facturation à la minute) :
        # Retell fournit soit duration_ms directement, soit les horodatages
        # de début/fin (en ms) — jamais utilisée jusqu'ici, la colonne
        # restait toujours à zéro malgré la donnée déjà transmise.
        duration_ms = call_data.get("duration_ms")
        if duration_ms is None:
            start_ts = call_data.get("start_timestamp")
            end_ts = call_data.get("end_timestamp")
            if start_ts is not None and end_ts is not None:
                duration_ms = end_ts - start_ts
        if duration_ms is not None and duration_ms >= 0:
            call.duration_seconds = round(duration_ms / 1000)

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

        # Consentement à l'enregistrement refusé (section 42/43) : la
        # classification vient de s'appuyer sur le contenu réel (nécessaire
        # au suivi commercial), mais le contenu détaillé lui-même ne doit
        # JAMAIS être conservé — seul le résultat (qualification, etc.) l'est.
        if call.recording_consent_refused:
            call.transcript = "[Non conservé — consentement à l'enregistrement refusé par l'interlocuteur]"
            call.summary = "[Non conservé — consentement à l'enregistrement refusé par l'interlocuteur]"

    db.commit()
    return {"status": "ok"}


@router.post("/retell/tools/withdraw-recording-consent")
async def withdraw_recording_consent(request: Request, db: Session = Depends(get_db)):
    """
    Outil en direct (section 42/43) : l'agent appelle ceci si l'interlocuteur
    indique ne pas vouloir être enregistré, mais souhaite que l'appel
    continue. Identifie l'appel via l'objet "call" transmis par Retell
    (args_at_root désactivé pour ce outil précisément, voir retell_provider),
    plus fiable qu'une recherche par numéro de téléphone.

    Résilience (section 29) : si l'appel n'est pas encore retrouvable (créé
    entre-temps par call_started, webhook parfois légèrement en retard), on
    répond quand même normalement à l'agent — l'important est de ne jamais
    interrompre la conversation pour une raison technique de notre côté.
    """
    payload = await request.json()
    call_id = payload.get("call", {}).get("call_id")

    if call_id:
        call = db.query(Call).filter(Call.provider_call_id == call_id).first()
        if call:
            call.recording_consent_refused = True
            db.commit()
            logger.info("Consentement à l'enregistrement retiré pour l'appel %s", call.id)
        else:
            logger.warning("withdraw_recording_consent : appel introuvable pour call_id=%s", call_id)
    else:
        logger.warning("withdraw_recording_consent : aucun call_id transmis dans la requête")

    return {"result": "D'accord, je continue sans enregistrer votre message."}


@router.post("/retell/tools/register-do-not-call")
async def register_do_not_call(request: Request, db: Session = Depends(get_db)):
    """
    Outil en direct (section 42/43, recommandation CNIL — "liste
    repoussoir") : l'agent appelle ceci dès que le prospect exprime
    explicitement ne plus vouloir être recontacté. Bloque le CONTACT (pas
    seulement cet appel) pour toutes les campagnes futures — retrouvé via
    Call.contact_id, lui-même identifié par call.call_id (voir
    withdraw_recording_consent pour le même principe).

    Résilience (section 29) : si le contact n'est pas retrouvable, on
    répond quand même normalement à l'agent, sans jamais bloquer la fin
    de l'appel pour une raison technique de notre côté.
    """
    payload = await request.json()
    call_id = payload.get("call", {}).get("call_id")

    if call_id:
        call = db.query(Call).filter(Call.provider_call_id == call_id).first()
        if call and call.contact_id:
            contact = db.query(Contact).filter(Contact.id == call.contact_id).first()
            if contact:
                contact.do_not_call = True
                contact.do_not_call_reason = "Demande explicite pendant un appel."
                contact.do_not_call_at = datetime.utcnow()
                db.commit()
                logger.info("Contact %s ajouté à la liste repoussoir (appel %s)", contact.id, call.id)
        else:
            logger.warning("register_do_not_call : appel ou contact introuvable pour call_id=%s", call_id)
    else:
        logger.warning("register_do_not_call : aucun call_id transmis dans la requête")

    return {"result": "C'est noté, vous ne serez plus recontacté(e). Je vous souhaite une bonne journée."}


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
