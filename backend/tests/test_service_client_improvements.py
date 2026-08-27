"""
Tests des améliorations du service client (section 12 du cahier des
charges) : priorité basée sur le contenu, notification de résolution,
consultation de ticket en direct, assignation.
"""
from unittest.mock import patch

from app.core.call_pipeline import _priority_from_content
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


# ---------- Priorité basée sur le contenu (point 2) ----------

def test_calm_customer_with_urgent_issue_gets_urgent_priority():
    """Test central : un client calme signalant un problème grave doit recevoir la priorité maximale."""
    priority = _priority_from_content(
        transcript="Client: Bonjour, j'ai remarqué que j'ai été débité deux fois ce mois-ci.",
        summary="Le client signale un double prélèvement.",
        sentiment="Neutre",
    )
    assert priority == "urgente"


def test_angry_customer_minor_issue_does_not_override_but_still_gets_negative_priority():
    priority = _priority_from_content(
        transcript="Client: C'est inadmissible, votre site est moche !",
        summary="Remarque esthétique sur le site web.",
        sentiment="Négatif",
    )
    assert priority == "haute"  # basé sur le ton, faute de mot-clé d'urgence réelle


def test_positive_call_without_urgent_keywords_gets_low_priority():
    priority = _priority_from_content(
        transcript="Client: Merci beaucoup, tout va bien.",
        summary="Appel de courtoisie.",
        sentiment="Positif",
    )
    assert priority == "basse"


def test_urgent_keyword_detected_even_with_positive_tone():
    priority = _priority_from_content(
        transcript="Client: Pas de souci, mais je voulais signaler que le service est en panne.",
        summary="Signalement de panne.",
        sentiment="Positif",
    )
    assert priority == "urgente"


# ---------- Notification de résolution (point 1) ----------

@patch("app.providers.messaging.mock.MockMessagingProvider.send_sms")
def test_resolving_ticket_notifies_customer_by_sms(mock_send_sms, client, db_session):
    from app.models.agent import Agent
    from app.models.contact import Contact
    from app.models.ticket import Ticket
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Service Client"}, headers=headers).json()
    contact = Contact(organization_id=org_id, phone="+33612700001")
    db_session.add(contact)
    db_session.flush()
    ticket = Ticket(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), contact_id=contact.id,
        subject="Problème de connexion", status="ouvert",
    )
    db_session.add(ticket)
    db_session.commit()

    response = client.patch(f"/tickets/{ticket.id}", json={"status": "résolu", "resolution_notes": "Réseau rétabli."}, headers=headers)

    assert response.status_code == 200
    mock_send_sms.assert_called_once()
    _, kwargs = mock_send_sms.call_args
    assert kwargs["to_number"] == "+33612700001"
    assert "Problème de connexion" in kwargs["body"]


@patch("app.providers.messaging.mock.MockMessagingProvider.send_sms")
def test_resolving_already_resolved_ticket_does_not_renotify(mock_send_sms, client, db_session):
    from app.models.contact import Contact
    from app.models.ticket import Ticket
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Service Client"}, headers=headers).json()
    contact = Contact(organization_id=org_id, phone="+33612700002")
    db_session.add(contact)
    db_session.flush()
    ticket = Ticket(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), contact_id=contact.id,
        subject="Test", status="résolu",
    )
    db_session.add(ticket)
    db_session.commit()

    client.patch(f"/tickets/{ticket.id}", json={"status": "résolu"}, headers=headers)
    mock_send_sms.assert_not_called()


def test_resolution_notification_failure_never_blocks_status_update(client, db_session):
    from app.models.contact import Contact
    from app.models.ticket import Ticket
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Service Client"}, headers=headers).json()
    contact = Contact(organization_id=org_id, phone="+33612700003")
    db_session.add(contact)
    db_session.flush()
    ticket = Ticket(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), contact_id=contact.id,
        subject="Test", status="ouvert",
    )
    db_session.add(ticket)
    db_session.commit()

    with patch("app.providers.messaging.mock.MockMessagingProvider.send_sms", side_effect=Exception("SMS indisponible")):
        response = client.patch(f"/tickets/{ticket.id}", json={"status": "résolu"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "résolu"


# ---------- Consultation de ticket en direct (point 3) ----------

def test_lookup_tickets_finds_existing_tickets_for_contact(client, db_session):
    from app.models.contact import Contact
    from app.models.ticket import Ticket
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent Service Client"}, headers=headers).json()
    contact = Contact(organization_id=uuid_module.UUID(org_id), phone="+33612700004")
    db_session.add(contact)
    db_session.flush()
    db_session.add(Ticket(
        organization_id=uuid_module.UUID(org_id), agent_id=uuid_module.UUID(agent["id"]), contact_id=contact.id,
        subject="Ticket existant", status="en_cours",
    ))
    db_session.commit()

    response = client.post(f"/tickets/tools/lookup?organization_id={org_id}", json={"guest_phone": "+33612700004"})
    body = response.json()
    assert body["found"] is True
    assert body["tickets"][0]["subject"] == "Ticket existant"


def test_lookup_tickets_returns_not_found_gracefully_for_unknown_contact(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    response = client.post(f"/tickets/tools/lookup?organization_id={org_id}", json={"guest_phone": "+33612700005"})
    assert response.status_code == 200
    assert response.json()["found"] is False


def test_lookup_tickets_isolated_between_organizations(client, db_session):
    from app.models.contact import Contact
    from app.models.ticket import Ticket
    import uuid as uuid_module

    headers_a = setup_org(client)
    headers_b = setup_org(client)
    org_a_id = headers_a["x-organization-id"]
    agent_a = client.post("/agents", json={"name": "Agent A"}, headers=headers_a).json()
    contact = Contact(organization_id=uuid_module.UUID(org_a_id), phone="+33612700006")
    db_session.add(contact)
    db_session.flush()
    db_session.add(Ticket(
        organization_id=uuid_module.UUID(org_a_id), agent_id=uuid_module.UUID(agent_a["id"]), contact_id=contact.id,
        subject="Confidentiel A", status="ouvert",
    ))
    db_session.commit()

    org_b_id = headers_b["x-organization-id"]
    response = client.post(f"/tickets/tools/lookup?organization_id={org_b_id}", json={"guest_phone": "+33612700006"})
    assert response.json()["found"] is False


# ---------- Assignation (point 5) ----------

def test_ticket_can_be_assigned_to_team_member(client, db_session):
    from app.models.contact import Contact
    from app.models.ticket import Ticket
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Service Client"}, headers=headers).json()
    ticket = Ticket(organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), subject="Test", status="ouvert")
    db_session.add(ticket)
    db_session.commit()

    response = client.patch(f"/tickets/{ticket.id}", json={"assigned_to": "Marie Diop"}, headers=headers)
    assert response.json()["assigned_to"] == "Marie Diop"


# ---------- Outil enregistré au provisionnement ----------

def test_ticket_lookup_tool_registered_when_ticketing_enabled(client):
    headers = setup_org(client)

    with patch("app.providers.voice.retell_provider.RetellProvider.create_llm") as mock_create_llm, \
         patch("app.providers.voice.retell_provider.RetellProvider.create_retell_agent") as mock_create_agent, \
         patch("app.providers.voice.retell_provider.RetellProvider.publish_agent"):
        mock_create_llm.return_value = {"llm_id": "llm_fake"}
        mock_create_agent.return_value = {"agent_id": "agent_fake"}

        with patch("app.api.routes.agents.settings") as mock_settings:
            mock_settings.voice_provider = "retell"
            mock_settings.retell_api_key = "fake_key"
            mock_settings.retell_default_llm_model = "gpt-4o-mini"
            mock_settings.retell_default_voice_id = "cartesia-Emma"
            mock_settings.public_base_url = "http://example.com"

            client.post("/agents", json={"name": "Agent Service Client", "ticketing_enabled": True}, headers=headers)

        _, kwargs = mock_create_llm.call_args
        tool_names = [t["name"] for t in kwargs["tools"]]
        assert "lookup_tickets" in tool_names
