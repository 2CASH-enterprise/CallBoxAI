"""
Tests de la prospection commerciale B2C/B2B (section 42 du cahier des
charges) : envoi WhatsApp et réservation de rendez-vous en direct.
"""
from datetime import datetime, timedelta

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


# ---------- WhatsApp ----------

def test_send_whatsapp_creates_contact_and_logs_message(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]

    response = client.post(
        f"/prospection/tools/send-whatsapp?organization_id={org_id}",
        json={"guest_phone": "+33612500001", "guest_name": "Awa", "content_summary": "Offre assurance santé famille"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["phone"] == "+33612500001"

    whatsapp_log = client.get("/whatsapp", headers=headers).json()
    assert len(whatsapp_log) == 1
    assert "Offre assurance santé famille" in whatsapp_log[0]["body"]


def test_send_whatsapp_reuses_existing_contact(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    client.post("/contacts", json={"phone": "+33612500002", "first_name": "Déjà là"}, headers=headers)

    client.post(
        f"/prospection/tools/send-whatsapp?organization_id={org_id}",
        json={"guest_phone": "+33612500002", "content_summary": "Test"},
    )

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["first_name"] == "Déjà là"


def test_whatsapp_log_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    org_a_id = headers_a["x-organization-id"]

    client.post(
        f"/prospection/tools/send-whatsapp?organization_id={org_a_id}",
        json={"guest_phone": "+33612500003", "content_summary": "Test"},
    )

    whatsapp_b = client.get("/whatsapp", headers=headers_b).json()
    assert len(whatsapp_b) == 0


# ---------- Réservation de rendez-vous (B2B) ----------

def test_book_meeting_creates_appointment(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent B2B"}, headers=headers).json()
    slot = (datetime.utcnow() + timedelta(days=3)).replace(microsecond=0).isoformat()

    response = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+33612500004", "guest_name": "Client B2B", "scheduled_at": slot, "notes": "BANT : budget confirmé, décideur identifié"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["appointment_id"]

    appointments = client.get("/appointments", headers=headers).json()
    assert len(appointments) == 1
    assert appointments[0]["notes"] == "BANT : budget confirmé, décideur identifié"


def test_book_meeting_rejects_past_slot(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent B2B"}, headers=headers).json()
    past_slot = (datetime.utcnow() - timedelta(days=1)).isoformat()

    response = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+33612500005", "scheduled_at": past_slot},
    )
    assert response.json()["success"] is False


def test_book_meeting_rejects_double_booking(client):
    """Test central : deux rendez-vous qui se chevauchent ne doivent jamais être acceptés."""
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent B2B"}, headers=headers).json()
    slot = (datetime.utcnow() + timedelta(days=5)).replace(microsecond=0).isoformat()

    first = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+33612500006", "scheduled_at": slot},
    )
    second = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+33612500007", "scheduled_at": slot},
    )

    assert first.json()["success"] is True
    assert second.json()["success"] is False
    assert "pris" in second.json()["error"]


def test_book_meeting_allows_non_overlapping_slots(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent B2B"}, headers=headers).json()
    slot1 = (datetime.utcnow() + timedelta(days=6, hours=0)).replace(microsecond=0).isoformat()
    slot2 = (datetime.utcnow() + timedelta(days=6, hours=2)).replace(microsecond=0).isoformat()

    first = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+33612500008", "scheduled_at": slot1},
    )
    second = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+33612500009", "scheduled_at": slot2},
    )

    assert first.json()["success"] is True
    assert second.json()["success"] is True


def test_book_meeting_isolated_between_organizations(client):
    """Le calendrier est partagé PAR ORGANISATION, pas entre organisations différentes."""
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    org_a_id = headers_a["x-organization-id"]
    org_b_id = headers_b["x-organization-id"]
    agent_a = client.post("/agents", json={"name": "Agent A"}, headers=headers_a).json()
    agent_b = client.post("/agents", json={"name": "Agent B"}, headers=headers_b).json()
    slot = (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat()

    first = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_a_id}&agent_id={agent_a['id']}",
        json={"guest_phone": "+33612500010", "scheduled_at": slot},
    )
    second = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_b_id}&agent_id={agent_b['id']}",
        json={"guest_phone": "+33612500011", "scheduled_at": slot},
    )

    assert first.json()["success"] is True
    assert second.json()["success"] is True  # même créneau, mais organisations différentes


def test_book_meeting_rejects_invalid_date_format(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent B2B"}, headers=headers).json()

    response = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+33612500012", "scheduled_at": "pas une date"},
    )
    assert response.json()["success"] is False


# ---------- Outils enregistrés au provisionnement ----------

def test_whatsapp_and_meeting_tools_registered_when_enabled(client):
    from unittest.mock import patch

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
                json={"name": "Agent Prospection B2B", "whatsapp_enabled": True, "meeting_booking_enabled": True},
                headers=headers,
            )

        _, kwargs = mock_create_llm.call_args
        tool_names = [t["name"] for t in kwargs["tools"]]
        assert "send_whatsapp_brochure" in tool_names
        assert "book_meeting" in tool_names
