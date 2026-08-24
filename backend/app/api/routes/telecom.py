"""
Outils télécom en direct (section 41 du cahier des charges — KYC simplifié).
Plutôt qu'un système de vérification de documents, on envoie simplement par
SMS le lien du KYC déjà existant chez le partenaire (opérateur télécom).
Même principe que les outils PMS : appelé par Retell PENDANT l'appel, sans
JWT (Retell ne peut pas s'authentifier comme un utilisateur du dashboard),
scopé par organization_id encodé dans l'URL au provisionnement.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.providers import get_messaging_provider
from app.models.agent import Agent
from app.models.contact import Contact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telecom", tags=["telecom"])


class SendKycLinkRequest(BaseModel):
    guest_phone: str
    guest_name: str | None = None


@router.post("/tools/send-kyc-link")
def tool_send_kyc_link(
    payload: SendKycLinkRequest,
    organization_id: uuid.UUID = Query(...),
    agent_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    """
    Envoie par SMS le lien KYC du partenaire au client, EN DIRECT pendant
    l'appel. Le contact est retrouvé (ou créé) par téléphone — même logique
    que les outils PMS (section 18).
    """
    logger.info("Outil send_kyc_link appelé : org=%s agent=%s guest_phone=%r", organization_id, agent_id, payload.guest_phone)

    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.organization_id == organization_id).first()
    if not agent or not agent.kyc_link_url:
        logger.warning("send_kyc_link : agent introuvable ou kyc_link_url non configuré")
        return {"success": False, "error": "Aucun lien KYC configuré pour cet agent."}

    contact = db.query(Contact).filter(
        Contact.organization_id == organization_id, Contact.phone == payload.guest_phone
    ).first()
    if not contact:
        contact = Contact(organization_id=organization_id, phone=payload.guest_phone, first_name=payload.guest_name)
        db.add(contact)
        db.flush()

    try:
        provider = get_messaging_provider(db, organization_id)
        provider.send_sms(
            to_number=payload.guest_phone,
            body=f"Voici votre lien de vérification d'identité : {agent.kyc_link_url}",
        )
        sms_sent = True
    except Exception:
        logger.exception("send_kyc_link : échec de l'envoi SMS")
        sms_sent = False

    if sms_sent:
        contact.status = "À rappeler"  # relance possible en attendant la vérification
    db.commit()

    if not sms_sent:
        return {"success": False, "error": "Échec de l'envoi du SMS. Réessayez ou transférez à un opérateur."}
    return {"success": True, "message": "Lien KYC envoyé par SMS."}
