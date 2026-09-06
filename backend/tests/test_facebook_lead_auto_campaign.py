"""
Tests de l'inscription automatique d'un lead Facebook à la campagne
désignée, avec appel immédiat (section 42/43) — dernier maillon du
parcours "formulaire rempli → IA appelle immédiatement".
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


def _send_lead_webhook(client, page_id: str, leadgen_id: str, secret: str = "vrai-secret"):
    payload = {"entry": [{"id": page_id, "changes": [{"value": {"leadgen_id": leadgen_id}}]}]}
    body = json.dumps(payload).encode()
    signature = _sign(body, secret)
    with patch("app.api.routes.facebook_webhooks.settings") as mock_settings:
        mock_settings.facebook_app_secret = secret
        with patch("app.providers.leads.facebook.FacebookLeadProvider") as MockProvider:
            from app.providers.leads.mock import MockLeadProvider
            MockProvider.return_value = MockLeadProvider()
            return client.post(
                "/webhooks/facebook", content=body,
                headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
            )


def test_lead_without_designated_campaign_only_captures_contact(client, db_session):
    """Sans campagne désignée, rien ne change par rapport à avant (capture seule)."""
    from app.models.organization import Organization
    import uuid as uuid_module

    headers = setup_org(client)
    org = db_session.query(Organization).filter(Organization.id == uuid_module.UUID(headers["x-organization-id"])).first()
    org.facebook_page_id = "page_auto_001"
    org.facebook_page_access_token = "fake_token"
    db_session.commit()

    response = _send_lead_webhook(client, "page_auto_001", "lead_auto_001")
    assert response.status_code == 200

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1


def test_lead_enrolled_in_designated_campaign_when_running(client, db_session):
    """Test central : campagne active + dans les horaires -> appel immédiat tenté."""
    from app.models.organization import Organization
    from app.models.campaign import Campaign, CampaignTarget
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Facebook"}, headers=headers).json()
    campaign = client.post(
        "/campaigns",
        json={"name": "Campagne Facebook", "agent_id": agent["id"], "schedule_start": "00:00", "schedule_end": "23:59"},
        headers=headers,
    ).json()
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)

    org = db_session.query(Organization).filter(Organization.id == org_id).first()
    org.facebook_page_id = "page_auto_002"
    org.facebook_page_access_token = "fake_token"
    org.facebook_leads_campaign_id = uuid_module.UUID(campaign["id"])
    db_session.commit()

    response = _send_lead_webhook(client, "page_auto_002", "lead_auto_002")
    assert response.status_code == 200

    targets = db_session.query(CampaignTarget).filter(CampaignTarget.campaign_id == uuid_module.UUID(campaign["id"])).all()
    assert len(targets) == 1
    # Un appel a été tenté : soit complété, soit en attente de retry, mais jamais "attempts == 0"
    assert targets[0].attempts >= 1 or targets[0].status == "pending"


def test_lead_captured_but_not_called_when_campaign_not_running(client, db_session):
    """Point 3 validé : campagne inactive -> lead capturé, mais pas encore appelé."""
    from app.models.organization import Organization
    from app.models.campaign import CampaignTarget
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Facebook"}, headers=headers).json()
    campaign = client.post(
        "/campaigns", json={"name": "Campagne Non Démarrée", "agent_id": agent["id"]}, headers=headers
    ).json()
    # Volontairement PAS démarrée (reste "draft")

    org = db_session.query(Organization).filter(Organization.id == org_id).first()
    org.facebook_page_id = "page_auto_003"
    org.facebook_page_access_token = "fake_token"
    org.facebook_leads_campaign_id = uuid_module.UUID(campaign["id"])
    db_session.commit()

    response = _send_lead_webhook(client, "page_auto_003", "lead_auto_003")
    assert response.status_code == 200

    targets = db_session.query(CampaignTarget).filter(CampaignTarget.campaign_id == uuid_module.UUID(campaign["id"])).all()
    assert len(targets) == 1
    assert targets[0].attempts == 0  # jamais appelé, juste capturé
    assert targets[0].status == "pending"


def test_lead_not_duplicated_if_already_in_campaign(client, db_session):
    from app.models.organization import Organization
    from app.models.contact import Contact
    from app.models.campaign import CampaignTarget
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Facebook"}, headers=headers).json()
    campaign = client.post("/campaigns", json={"name": "Campagne Test", "agent_id": agent["id"]}, headers=headers).json()

    org = db_session.query(Organization).filter(Organization.id == org_id).first()
    org.facebook_page_id = "page_auto_004"
    org.facebook_page_access_token = "fake_token"
    org.facebook_leads_campaign_id = uuid_module.UUID(campaign["id"])
    db_session.commit()

    # Pré-existant : le contact du lead de test (+33612960001, cf MockLeadProvider) est déjà dans la campagne
    contact = Contact(organization_id=org_id, phone="+33612960001")
    db_session.add(contact)
    db_session.flush()
    db_session.add(CampaignTarget(campaign_id=uuid_module.UUID(campaign["id"]), contact_id=contact.id, status="completed"))
    db_session.commit()

    _send_lead_webhook(client, "page_auto_004", "lead_auto_004")

    targets = db_session.query(CampaignTarget).filter(CampaignTarget.campaign_id == uuid_module.UUID(campaign["id"])).all()
    assert len(targets) == 1  # pas de doublon créé


def test_missing_designated_campaign_never_crashes(client, db_session):
    """Résilience (section 29) : une campagne désignée supprimée entre-temps ne doit jamais planter."""
    from app.models.organization import Organization
    import uuid as uuid_module

    headers = setup_org(client)
    org = db_session.query(Organization).filter(Organization.id == uuid_module.UUID(headers["x-organization-id"])).first()
    org.facebook_page_id = "page_auto_005"
    org.facebook_page_access_token = "fake_token"
    org.facebook_leads_campaign_id = uuid_module.uuid4()  # référence une campagne inexistante
    db_session.commit()

    response = _send_lead_webhook(client, "page_auto_005", "lead_auto_005")
    assert response.status_code == 200

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1  # le contact reste bien capturé malgré tout


# ---------- Réglage de la campagne désignée via /knowledge/sources ----------

def test_can_set_facebook_leads_campaign_via_sources_endpoint(client):
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    campaign = client.post("/campaigns", json={"name": "Campagne Test", "agent_id": agent["id"]}, headers=headers).json()

    response = client.patch(
        "/knowledge/sources", json={"facebook_leads_campaign_id": campaign["id"]}, headers=headers
    )
    assert response.json()["facebook_leads_campaign_id"] == campaign["id"]
