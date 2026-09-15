"""
Enregistrement des erreurs applicatives (monitoring Super Admin).
"""
import logging
import traceback

from app.models.error_log import ErrorLog

logger = logging.getLogger(__name__)


def log_error(db, source: str, message: str, organization_id=None, exc: Exception | None = None) -> None:
    """
    Enregistre une erreur en base pour le monitoring Super Admin, EN PLUS du
    journal serveur habituel (logger), jamais à sa place. Résilience
    (section 29) : un échec d'écriture de ce journal ne doit jamais faire
    planter le code appelant — c'est un outil de visibilité, pas une
    dépendance critique.
    """
    try:
        details = traceback.format_exc() if exc else None
        db.add(ErrorLog(
            organization_id=organization_id, source=source, message=message, details=details,
        ))
        db.commit()
    except Exception:
        logger.exception("Échec de l'enregistrement dans le journal d'erreurs (source=%s)", source)
        db.rollback()
