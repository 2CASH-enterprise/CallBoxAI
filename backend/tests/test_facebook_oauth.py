"""
Tests du flux "Connecter avec Facebook" (section 42/43 — OAuth Facebook
Login for Business) : évite au client de manipuler le Graph API Explorer.
"""
from unittest.mock import patch, MagicMock

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


# ---------- /authorize ----------

def test_authorize_url_requires_authentication(client):
    response = client.get("/oauth/facebook/authorize")
    assert response.status_code in (401, 403)


def test_authorize_url_contains_signed_state(client):
    headers = setup_org(client)
    with patch("app.api.routes.facebook_oauth.settings") as mock_settings:
        mock_settings.facebook_app_id = "123456"
        mock_settings.facebook_app_secret = "test_secret"
        mock_settings.public_base_url = "https://api.callbox-ai.com"
        response = client.get("/oauth/facebook/authorize", headers=headers)

    assert response.status_code == 200
    url = response.json()["authorize_url"]
    assert "client_id=123456" in url
    assert "state=" in url
    assert headers["x-organization-id"] in url


# ---------- /callback ----------

def test_callback_redirects_with_error_if_denied(client):
    with patch("app.api.routes.facebook_oauth.settings") as mock_settings:
        mock_settings.frontend_base_url = "https://app.callbox-ai.com"
        response = client.get("/oauth/facebook/callback?error=access_denied", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "facebook_error" in response.headers["location"]


def test_callback_rejects_invalid_state_signature(client):
    with patch("app.api.routes.facebook_oauth.settings") as mock_settings:
        mock_settings.frontend_base_url = "https://app.callbox-ai.com"
        mock_settings.facebook_app_secret = "test_secret"
        response = client.get(
            "/oauth/facebook/callback?code=fake_code&state=some-org-id.signature-invalide",
            follow_redirects=False,
        )

    assert "facebook_error=invalid_state" in response.headers["location"]


def test_callback_completes_full_flow_and_saves_page_credentials(client, db_session):
    from app.api.routes.facebook_oauth import _sign_state
    from app.models.organization import Organization
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])

    with patch("app.api.routes.facebook_oauth.settings") as mock_settings:
        mock_settings.facebook_app_secret = "test_secret"
        mock_settings.facebook_app_id = "123456"
        mock_settings.public_base_url = "https://api.callbox-ai.com"
        mock_settings.frontend_base_url = "https://app.callbox-ai.com"
        valid_state = _sign_state(org_id)

        mock_token_response = MagicMock()
        mock_token_response.json.return_value = {"access_token": "fake_user_token"}
        mock_token_response.raise_for_status.return_value = None

        mock_pages_response = MagicMock()
        mock_pages_response.json.return_value = {
            "data": [{"id": "page_123", "access_token": "fake_page_token", "name": "Ma Page Test"}]
        }
        mock_pages_response.raise_for_status.return_value = None

        with patch("httpx.get", side_effect=[mock_token_response, mock_pages_response]):
            with patch("app.providers.leads.facebook.subscribe_page_to_leadgen_webhook", return_value=True):
                response = client.get(
                    f"/oauth/facebook/callback?code=fake_code&state={valid_state}",
                    follow_redirects=False,
                )

    assert "facebook_connected=1" in response.headers["location"]
    assert "facebook_subscription=ok" in response.headers["location"]

    organization = db_session.query(Organization).filter(Organization.id == org_id).first()
    assert organization.facebook_page_id == "page_123"
    assert organization.facebook_page_access_token == "fake_page_token"


def test_callback_handles_no_pages_gracefully(client):
    from app.api.routes.facebook_oauth import _sign_state
    from tests.conftest import register_user
    import uuid as uuid_module

    token, org_id = register_user(client)

    with patch("app.api.routes.facebook_oauth.settings") as mock_settings:
        mock_settings.facebook_app_secret = "test_secret"
        mock_settings.facebook_app_id = "123456"
        mock_settings.public_base_url = "https://api.callbox-ai.com"
        mock_settings.frontend_base_url = "https://app.callbox-ai.com"
        valid_state = _sign_state(uuid_module.UUID(org_id))

        mock_token_response = MagicMock()
        mock_token_response.json.return_value = {"access_token": "fake_user_token"}
        mock_token_response.raise_for_status.return_value = None

        mock_pages_response = MagicMock()
        mock_pages_response.json.return_value = {"data": []}
        mock_pages_response.raise_for_status.return_value = None

        with patch("httpx.get", side_effect=[mock_token_response, mock_pages_response]):
            response = client.get(
                f"/oauth/facebook/callback?code=fake_code&state={valid_state}",
                follow_redirects=False,
            )

    assert "facebook_error=no_pages" in response.headers["location"]


def test_callback_resilient_to_graph_api_failure(client):
    """Résilience (section 29) : un échec de l'API Graph ne doit jamais casser la redirection."""
    from app.api.routes.facebook_oauth import _sign_state
    from tests.conftest import register_user
    import uuid as uuid_module

    token, org_id = register_user(client)

    with patch("app.api.routes.facebook_oauth.settings") as mock_settings:
        mock_settings.facebook_app_secret = "test_secret"
        mock_settings.facebook_app_id = "123456"
        mock_settings.public_base_url = "https://api.callbox-ai.com"
        mock_settings.frontend_base_url = "https://app.callbox-ai.com"
        valid_state = _sign_state(uuid_module.UUID(org_id))

        with patch("httpx.get", side_effect=Exception("Réseau indisponible")):
            response = client.get(
                f"/oauth/facebook/callback?code=fake_code&state={valid_state}",
                follow_redirects=False,
            )

    assert response.status_code in (302, 307)
    assert "facebook_error=exchange_failed" in response.headers["location"]
