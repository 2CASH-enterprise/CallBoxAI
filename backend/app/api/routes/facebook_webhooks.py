"""
Webhook Facebook Lead Ads (section 42/43 du cahier des charges, point 3/3
de la brique de compliance) — dernière pièce du tunnel B2C conforme :

Facebook Ad → Formulaire (avec question de consentement) → ce webhook →
Consent Ledger (point 1) → disponible pour le Compliance Check (point 2)
avant tout appel sortant.

Ces endpoints ne sont PAS protégés par JWT : c'est Meta qui nous appelle,
pas un utilisateur connecté — l'authenticité est vérifiée par la signature
de la requête (X-Hub-Signature-256), pas par un jeton de session.
"""
import hashlib
import hmac
import logging
import uuid

from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.organization import Organization
from app.models.contact import Contact
from app.models.consent_record import ConsentRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/facebook", tags=["facebook-webhooks"])


@router.get("")
def verify_webhook(request: Request):
    """
    Meta appelle cet endpoint UNE FOIS, au moment de l'abonnement au
    webhook dans leur interface — il faut renvoyer exactement la valeur de
    hub.challenge si hub.verify_token correspond à notre jeton configuré.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token and settings.facebook_webhook_verify_token and token == settings.facebook_webhook_verify_token:
        return Response(content=challenge or "", media_type="text/plain")

    logger.warning("Vérification du webhook Facebook refusée : jeton invalide ou non configuré")
    return Response(status_code=403)


def _verify_signature(body: bytes, signature_header: str | None) -> bool:
    """
    Vérifie que la requête provient bien de Meta (section 24 — ne jamais
    faire confiance à une donnée non vérifiée), via HMAC-SHA256 avec le
    secret de l'app Meta.
    """
    if not settings.facebook_app_secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        settings.facebook_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.post("")
async def receive_lead_notification(request: Request, db: Session = Depends(get_db)):
    """
    Meta appelle cet endpoint à chaque nouveau lead soumis sur un formulaire
    abonné. Le corps ne contient qu'un identifiant (leadgen_id) — il faut un
    second appel (API Graph) pour obtenir les vraies réponses du formulaire.
    """
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(body, signature):
        logger.warning("Signature Facebook invalide — notification ignorée")
        return {"status": "ignored"}

    payload = await request.json()
    _process_facebook_payload(db, payload)

    return {"status": "ok"}


def _process_facebook_payload(db, payload: dict) -> None:
    from app.providers.leads.facebook import FacebookLeadProvider

    provider = FacebookLeadProvider()

    for entry in payload.get("entry", []):
        page_id = entry.get("id")
        organization = db.query(Organization).filter(Organization.facebook_page_id == page_id).first()
        if not organization or not organization.facebook_page_access_token:
            logger.warning("Lead Facebook reçu pour une page non configurée (page_id=%s) — ignoré", page_id)
            continue

        for change in entry.get("changes", []):
            leadgen_id = change.get("value", {}).get("leadgen_id")
            if not leadgen_id:
                continue

            try:
                details = provider.fetch_lead_details(leadgen_id, organization.facebook_page_access_token)
            except Exception:
                logger.exception("Échec de récupération du détail du lead Facebook %s", leadgen_id)
                continue

            _record_lead_as_consent(db, organization, change.get("value", {}), details)


def _record_lead_as_consent(db, organization: Organization, change_value: dict, details: dict) -> None:
    phone = details.get("phone")
    if not phone:
        logger.warning("Lead Facebook sans numéro de téléphone exploitable — ignoré")
        return

    contact = db.query(Contact).filter(
        Contact.organization_id == organization.id, Contact.phone == phone
    ).first()
    if not contact:
        contact = Contact(organization_id=organization.id, phone=phone, first_name=details.get("name"))
        db.add(contact)
        db.flush()

    db.add(ConsentRecord(
        organization_id=organization.id,
        contact_id=contact.id,
        source="facebook_lead_ads",
        campaign_reference=change_value.get("ad_id") or change_value.get("form_id"),
        consent_text=details.get("raw_field_summary", ""),
    ))
    db.commit()
    logger.info("Lead Facebook enregistré : contact=%s org=%s", contact.id, organization.id)
