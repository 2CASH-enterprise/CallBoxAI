"""
Synchronisation de la base de connaissances Retell (section 10/42 du
cahier des charges) — UNE base par organisation, partagée par tous ses
agents, créée à la première source ajoutée puis mise à jour de façon
incrémentale (jamais recréée entièrement).

Résilience (section 29) : un échec de synchronisation ne doit JAMAIS
bloquer l'action locale (créer un document, enregistrer un site web...) —
la base de connaissances Retell reste alors simplement en retard d'une
source, sans casser le reste du produit.
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.organization import Organization

logger = logging.getLogger(__name__)


def sync_knowledge_source(
    db: Session,
    organization: Organization,
    texts: list[dict] | None = None,
    urls: list[str] | None = None,
) -> None:
    if settings.voice_provider != "retell" or not settings.retell_api_key:
        return
    if not texts and not urls:
        return

    try:
        from app.providers.voice.retell_provider import RetellProvider

        provider = RetellProvider(api_key=settings.retell_api_key, agent_id="")

        if organization.retell_knowledge_base_id:
            provider.add_knowledge_base_sources(organization.retell_knowledge_base_id, texts=texts, urls=urls)
        else:
            result = provider.create_knowledge_base(f"CallBoxAI - {organization.name}", texts=texts, urls=urls)
            organization.retell_knowledge_base_id = result["knowledge_base_id"]
            db.commit()

        logger.info(
            "Base de connaissances Retell synchronisée pour l'organisation %s (kb=%s)",
            organization.id, organization.retell_knowledge_base_id,
        )
    except Exception:
        logger.exception(
            "Échec de la synchronisation de la base de connaissances Retell pour l'organisation %s",
            organization.id,
        )
