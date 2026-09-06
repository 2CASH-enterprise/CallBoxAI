"""
Flux "Connecter avec Facebook" (section 42/43 — OAuth Facebook Login for
Business) : évite au client de devoir manipuler le Graph API Explorer,
copier un jeton, ou distinguer un jeton utilisateur d'un jeton de page —
toute la mécanique qu'on a dû faire manuellement est ici automatisée.

Le endpoint /authorize est protégé par JWT (le client doit être connecté à
son organisation). Le endpoint /callback ne l'est PAS : c'est Facebook qui
y redirige le navigateur directement, sans jeton de session — l'organisation
concernée est retrouvée via un paramètre `state` signé (HMAC), pour éviter
qu'un tiers ne puisse associer sa propre page Facebook au compte d'un autre
client (section 24 : ne jamais faire confiance à une donnée non vérifiée).
"""
import hashlib
import hmac
import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.organization import Organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth/facebook", tags=["facebook-oauth"])

GRAPH_API_VERSION = "v21.0"
OAUTH_SCOPES = "pages_show_list,pages_manage_metadata,leads_retrieval,pages_read_engagement,business_management"


def _callback_url() -> str:
    return f"{settings.public_base_url.rstrip('/')}/oauth/facebook/callback"


def _sign_state(organization_id: uuid.UUID) -> str:
    """Signe l'organisation d'origine (HMAC) pour la retrouver de façon fiable au retour de Facebook."""
    org_str = str(organization_id)
    signature = hmac.new(settings.facebook_app_secret.encode(), org_str.encode(), hashlib.sha256).hexdigest()
    return f"{org_str}.{signature}"


def _verify_state(state: str) -> uuid.UUID | None:
    try:
        org_str, signature = state.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(settings.facebook_app_secret.encode(), org_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        return uuid.UUID(org_str)
    except ValueError:
        return None


@router.get("/authorize")
def get_authorize_url(
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Retourne l'URL vers laquelle rediriger le navigateur du client pour
    démarrer la connexion Facebook — le frontend fait ensuite
    `window.location.href = authorize_url`.
    """
    state = _sign_state(organization_id)
    params = (
        f"client_id={settings.facebook_app_id}"
        f"&redirect_uri={_callback_url()}"
        f"&state={state}"
        f"&scope={OAUTH_SCOPES}"
        f"&response_type=code"
    )
    return {"authorize_url": f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?{params}"}


@router.get("/callback")
def oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Facebook redirige ici après que le client a autorisé (ou refusé) la
    connexion. Résilience (section 29) : toute erreur ramène simplement le
    client vers le dashboard avec un message clair, jamais une page cassée.
    """
    frontend_url = settings.frontend_base_url.rstrip("/") or "https://app.callbox-ai.com"
    redirect_base = f"{frontend_url}/knowledge"

    if error or not code or not state:
        logger.warning("Callback OAuth Facebook : refusé ou incomplet (error=%r)", error)
        return RedirectResponse(f"{redirect_base}?facebook_error=refused")

    organization_id = _verify_state(state)
    if not organization_id:
        logger.warning("Callback OAuth Facebook : state invalide ou signature incorrecte")
        return RedirectResponse(f"{redirect_base}?facebook_error=invalid_state")

    try:
        token_response = httpx.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token",
            params={
                "client_id": settings.facebook_app_id,
                "redirect_uri": _callback_url(),
                "client_secret": settings.facebook_app_secret,
                "code": code,
            },
            timeout=10.0,
        )
        token_response.raise_for_status()
        user_access_token = token_response.json()["access_token"]

        pages_response = httpx.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/accounts",
            params={"access_token": user_access_token},
            timeout=10.0,
        )
        pages_response.raise_for_status()
        pages = pages_response.json().get("data", [])
    except Exception:
        logger.exception("Callback OAuth Facebook : échec de l'échange de code ou de la récupération des pages")
        return RedirectResponse(f"{redirect_base}?facebook_error=exchange_failed")

    if not pages:
        logger.warning("Callback OAuth Facebook : aucune page trouvée pour ce compte (organisation=%s)", organization_id)
        return RedirectResponse(f"{redirect_base}?facebook_error=no_pages")

    # Simplification (section 42/43) : sélectionne la première page —
    # suffisant pour l'immense majorité des clients qui ne gèrent qu'une
    # seule page. Une vraie sélection multi-pages est une amélioration
    # possible si un client en a réellement besoin.
    page = pages[0]
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        return RedirectResponse(f"{redirect_base}?facebook_error=organization_not_found")

    organization.facebook_page_id = page["id"]
    organization.facebook_page_access_token = page["access_token"]
    db.commit()

    try:
        from app.providers.leads.facebook import subscribe_page_to_leadgen_webhook

        subscribe_page_to_leadgen_webhook(page["id"], page["access_token"])
    except Exception:
        logger.exception("Callback OAuth Facebook : abonnement au webhook échoué pour la page %s", page["id"])
        return RedirectResponse(f"{redirect_base}?facebook_connected=1&facebook_subscription=failed")

    return RedirectResponse(f"{redirect_base}?facebook_connected=1&facebook_subscription=ok")
