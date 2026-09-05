"""
Tests de l'intégration Facebook Lead Ads (section 42/43 du cahier des
charges, point 3/3 de la brique de compliance).
"""
import hashlib
import hmac
import json
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------- Vérification du webhook (GET) ----------

def test_webhook_verification_succeeds_with_correct_token(client):
    with patch("app.api.routes.facebook_webhooks.settings") as mock_settings:
        mock_settings.facebook_webhook_verify_token = "mon-jeton-secret"
        response = client.get(
            "/webhooks/facebook",
            params={"hub.mode": "subscribe", "hub.verify_token": "mon-jeton-secret", "hub.challenge": "12345"},
        )
    assert response.status_code == 200
    assert response.text == "12345"


def test_webhook_verification_rejected_with_wrong_token(client):
    with patch("app.api.routes.facebook_webhooks.settings") as mock_settings:
        mock_settings.facebook_webhook_verify_token = "le-bon-jeton"
        response = client.get(
            "/webhooks/facebook",
            params={"hub.mode": "subscribe", "hub.verify_token": "mauvais-jeton", "hub.challenge": "12345"},
        )
    assert response.status_code == 403


# ---------- Réception d'un lead (POST) ----------

def test_lead_notification_rejected_without_valid_signature(client, db_session):
    from app.models.organization import Organization
    import uuid as uuid_module

    headers = setup_org(client)
    org = db_session.query(Organization).filter(Organization.id == uuid_module.UUID(headers["x-organization-id"])).first()
    org.facebook_page_id = "page_test_001"
    org.facebook_page_access_token = "fake_token"
    db_session.commit()

    body = json.dumps({"entry": [{"id": "page_test_001", "changes": [{"value": {"leadgen_id": "lead_001"}}]}]}).encode()

    with patch("app.api.routes.facebook_webhooks.settings") as mock_settings:
        mock_settings.facebook_app_secret = "vrai-secret"
        response = client.post(
            "/webhooks/facebook", content=body, headers={"X-Hub-Signature-256": "sha256=invalide", "Content-Type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    # Aucun contact ni consentement créé
    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 0


def test_lead_notification_creates_contact_and_consent_with_valid_signature(client, db_session):
    from app.models.organization import Organization
    from app.providers.leads.mock import MockLeadProvider
    import uuid as uuid_module

    headers = setup_org(client)
    org = db_session.query(Organization).filter(Organization.id == uuid_module.UUID(headers["x-organization-id"])).first()
    org.facebook_page_id = "page_test_002"
    org.facebook_page_access_token = "fake_token"
    db_session.commit()

    payload = {"entry": [{"id": "page_test_002", "changes": [{"value": {"leadgen_id": "lead_002", "ad_id": "ad_campagne_rentree"}}]}]}
    body = json.dumps(payload).encode()
    secret = "vrai-secret"
    signature = _sign(body, secret)

    with patch("app.api.routes.facebook_webhooks.settings") as mock_settings:
        mock_settings.facebook_app_secret = secret
        with patch("app.providers.leads.facebook.FacebookLeadProvider", return_value=MockLeadProvider()):
            response = client.post(
                "/webhooks/facebook", content=body, headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["phone"] == "+33612960001"

    consent_history = client.get(f"/consent?contact_id={contacts[0]['id']}", headers=headers).json()
    assert len(consent_history) == 1
    assert consent_history[0]["source"] == "facebook_lead_ads"
    assert consent_history[0]["campaign_reference"] == "ad_campagne_rentree"
    assert "consentement_appel" in consent_history[0]["consent_text"]


def test_lead_notification_ignored_for_unknown_page(client, db_session):
    """Résilience (section 29) : un lead pour une page non configurée ne doit jamais planter."""
    payload = {"entry": [{"id": "page_inconnue", "changes": [{"value": {"leadgen_id": "lead_003"}}]}]}
    body = json.dumps(payload).encode()
    secret = "vrai-secret"
    signature = _sign(body, secret)

    with patch("app.api.routes.facebook_webhooks.settings") as mock_settings:
        mock_settings.facebook_app_secret = secret
        response = client.post(
            "/webhooks/facebook", content=body, headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"  # traité sans erreur, juste ignoré en interne


def test_lead_reuses_existing_contact_by_phone(client, db_session):
    from app.models.organization import Organization
    from app.providers.leads.mock import MockLeadProvider
    import uuid as uuid_module

    headers = setup_org(client)
    org = db_session.query(Organization).filter(Organization.id == uuid_module.UUID(headers["x-organization-id"])).first()
    org.facebook_page_id = "page_test_004"
    org.facebook_page_access_token = "fake_token"
    db_session.commit()
    client.post("/contacts", json={"phone": "+33612960001", "first_name": "Déjà là"}, headers=headers)

    payload = {"entry": [{"id": "page_test_004", "changes": [{"value": {"leadgen_id": "lead_004"}}]}]}
    body = json.dumps(payload).encode()
    secret = "vrai-secret"
    signature = _sign(body, secret)

    with patch("app.api.routes.facebook_webhooks.settings") as mock_settings:
        mock_settings.facebook_app_secret = secret
        with patch("app.providers.leads.facebook.FacebookLeadProvider", return_value=MockLeadProvider()):
            client.post(
                "/webhooks/facebook", content=body, headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
            )

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1  # pas de doublon
    assert contacts[0]["first_name"] == "Déjà là"


# ---------- Réglage des champs Facebook via /knowledge/sources ----------

def test_can_configure_facebook_page_via_sources_endpoint(client):
    headers = setup_org(client)
    response = client.patch(
        "/knowledge/sources",
        json={"facebook_page_id": "123456", "facebook_page_access_token": "token_secret"},
        headers=headers,
    )
    assert response.json()["facebook_page_id"] == "123456"

    sources = client.get("/knowledge/sources", headers=headers).json()
    assert sources["facebook_page_id"] == "123456"
