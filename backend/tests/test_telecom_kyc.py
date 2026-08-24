"""
Tests du KYC simplifié pour les opérateurs télécom (section 41 du cahier
des charges) : envoi du lien KYC du partenaire par SMS, en direct pendant
l'appel — pas de vérification de documents, juste la transmission du lien.
"""
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_kyc_agent(client, headers, **overrides):
    payload = {
        "name": "Agent Télécom",
        "category": "telecom",
        "kyc_enabled": True,
        "kyc_link_url": "https://kyc.orange.sn/verification/abc123",
    }
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def test_agent_stores_kyc_fields(client):
    headers = setup_org(client)
    agent = create_kyc_agent(client, headers)
    assert agent["kyc_enabled"] is True
    assert agent["kyc_link_url"] == "https://kyc.orange.sn/verification/abc123"


def test_send_kyc_link_creates_contact_and_sends_sms(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = create_kyc_agent(client, headers)

    response = client.post(
        f"/telecom/tools/send-kyc-link?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+221770000001", "guest_name": "Awa"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["phone"] == "+221770000001"
    assert contacts[0]["status"] == "À rappeler"

    sms_log = client.get("/sms", headers=headers).json()
    assert len(sms_log) == 1
    assert "https://kyc.orange.sn/verification/abc123" in sms_log[0]["body"]


def test_send_kyc_link_reuses_existing_contact(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = create_kyc_agent(client, headers)
    client.post("/contacts", json={"phone": "+221770000002", "first_name": "Déjà là"}, headers=headers)

    client.post(
        f"/telecom/tools/send-kyc-link?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+221770000002"},
    )

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["first_name"] == "Déjà là"


def test_send_kyc_link_fails_gracefully_without_configured_link(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent sans KYC"}, headers=headers).json()

    response = client.post(
        f"/telecom/tools/send-kyc-link?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+221770000003"},
    )
    assert response.status_code == 200  # jamais d'erreur HTTP brute pour l'agent
    assert response.json()["success"] is False


def test_send_kyc_link_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    org_b_id = headers_b["x-organization-id"]
    agent_a = create_kyc_agent(client, headers_a)

    # B ne doit pas pouvoir utiliser l'agent de A
    response = client.post(
        f"/telecom/tools/send-kyc-link?organization_id={org_b_id}&agent_id={agent_a['id']}",
        json={"guest_phone": "+221770000004"},
    )
    assert response.json()["success"] is False

    contacts_b = client.get("/contacts", headers=headers_b).json()
    assert len(contacts_b) == 0


def test_kyc_tool_registered_when_agent_has_kyc_enabled(client):
    """Vérifie que l'outil send_kyc_link est bien transmis à Retell lors du provisionnement."""
    headers = setup_org(client)

    with patch("app.providers.voice.retell_provider.RetellProvider.create_llm") as mock_create_llm, \
         patch("app.providers.voice.retell_provider.RetellProvider.create_retell_agent") as mock_create_agent, \
         patch("app.providers.voice.retell_provider.RetellProvider.publish_agent") as mock_publish:
        mock_create_llm.return_value = {"llm_id": "llm_fake"}
        mock_create_agent.return_value = {"agent_id": "agent_fake"}
        mock_publish.return_value = {}

        with patch("app.api.routes.agents.settings") as mock_settings:
            mock_settings.voice_provider = "retell"
            mock_settings.retell_api_key = "fake_key"
            mock_settings.retell_default_llm_model = "gpt-4o-mini"
            mock_settings.retell_default_voice_id = "cartesia-Emma"
            mock_settings.public_base_url = "http://example.com"

            client.post(
                "/agents",
                json={"name": "Agent Télécom", "kyc_enabled": True, "kyc_link_url": "https://kyc.test/x"},
                headers=headers,
            )

        _, kwargs = mock_create_llm.call_args
        tool_names = [t["name"] for t in kwargs["tools"]]
        assert "send_kyc_link" in tool_names


def test_telecom_category_uses_adapted_vocabulary(client):
    """Vérifie que la catégorie 'telecom' évite le vocabulaire commercial générique."""
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent Télécom", "category": "telecom"}, headers=headers).json()

    seen = set()
    for _ in range(30):
        call = client.post(
            "/calls", json={"agent_id": agent["id"], "to_number": "+221770000005", "from_number": "+221780000000"}, headers=headers
        ).json()
        seen.add(call["qualification"])

    assert "Prospect chaud" not in seen and "Prospect tiède" not in seen
    assert seen <= {"Prêt à activer", "À relancer", "Sans suite", "À suivre par un humain"}
