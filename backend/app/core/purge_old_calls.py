"""
Purge automatique des appels anciens (section 42/43, recommandation CNIL) :
le contenu détaillé (transcript, résumé) d'un appel n'est jamais conservé
au-delà de 6 mois, sauf exemption explicite (retention_hold, ex. litige en
cours). Seul le résultat de qualification reste, indéfiniment — nécessaire
au suivi commercial, jamais lui-même une donnée "d'enregistrement".

Utilisation :
  - Manuellement / à la demande : POST /admin/purge-old-calls (Super Admin)
  - Automatiquement : tâche planifiée (cron) exécutant, sur le serveur :
      docker compose exec -T backend python -m app.core.purge_old_calls
    Celery n'étant pas encore branché (section 40), c'est la même approche
    que la sauvegarde quotidienne de la base de données.
"""
import logging
from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models.call import Call

logger = logging.getLogger(__name__)

RETENTION_MONTHS = 6
PURGE_PLACEHOLDER = "[Non conservé — purge automatique après {} mois]".format(RETENTION_MONTHS)


def run_purge(db=None) -> int:
    """
    Retourne le nombre d'appels purgés. Accepte une session existante (utile
    pour les tests, ou une future intégration Celery) — sans session fournie,
    en crée une nouvelle et la referme proprement à la fin.
    """
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_MONTHS * 30)
        calls_to_purge = (
            db.query(Call)
            .filter(
                Call.started_at < cutoff,
                Call.retention_hold.is_(False),
                Call.transcript.isnot(None),
                Call.transcript != PURGE_PLACEHOLDER,
            )
            .all()
        )
        for call in calls_to_purge:
            call.transcript = PURGE_PLACEHOLDER
            call.summary = PURGE_PLACEHOLDER

        db.commit()
        logger.info("Purge automatique des appels : %d appel(s) purgé(s) (au-delà de %d mois).", len(calls_to_purge), RETENTION_MONTHS)
        return len(calls_to_purge)
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = run_purge()
    print(f"{count} appel(s) purgé(s).")
