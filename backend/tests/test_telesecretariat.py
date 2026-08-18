"""
Tests du télé-secrétariat : horaires d'ouverture, prise de message
automatique hors horaires (section 12 du cahier des charges).
"""
from datetime import datetime, timedelta

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent_with_hours(client, headers, **overrides):
    payload = {"name": "Agent secrétariat"}
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def create_inbound_call(client, headers, agent_id, contact_id=None):
    body = {"agent_id": agent_id, "to_number": "+221780000000", "from_number": "+221770000000", "direction": "inbound"}
    if contact_id:
        body["contact_id"] = contact_id
    return client.post("/calls", json=body, headers=headers)


def test_agent_without_hours_is_always_available(client):
    """Sans horaires configurés, un appel entrant se déroule normalement (pas de prise de message)."""
    headers = setup_org(client)
    agent = create_agent_with_hours(client, headers)
    response = create_inbound_call(client, headers, agent["id"])
    call = response.json()
    assert call["status"] != "message_taken"


def test_inbound_call_outside_hours_takes_a_message(client):
    """
    Fenêtre horaire impossible à atteindre (03:00-03:01) : tout appel entrant
    doit systématiquement basculer en prise de message.
    """
    headers = setup_org(client)
    agent = create_agent_with_hours(client, headers, business_hours_start="03:00", business_hours_end="03:01")
    contact = client.post("/contacts", json={"phone": "+221770000001", "first_name": "Awa"}, headers=headers).json()

    response = create_inbound_call(client, headers, agent["id"], contact_id=contact["id"])
    call = response.json()
    assert call["status"] == "message_taken"
    assert call["action_taken"] == "Message pris"

    messages = client.get("/messages", headers=headers).json()
    assert len(messages) == 1
    assert messages[0]["caller_name"] == "Awa"
    assert messages[0]["status"] == "new"
    assert messages[0]["callback_requested"] is True

    # Le contact doit passer en "À rappeler" (section 18)
    updated_contact = client.get("/contacts", headers=headers).json()[0]
    assert updated_contact["status"] == "À rappeler"


def test_inbound_call_within_wide_hours_does_not_take_message(client):
    """Avec une large fenêtre couvrant l'heure actuelle, pas de prise de message."""
    headers = setup_org(client)
    agent = create_agent_with_hours(client, headers, business_hours_start="00:00", business_hours_end="23:59")
    response = create_inbound_call(client, headers, agent["id"])
    assert response.json()["status"] != "message_taken"


def test_outbound_calls_ignore_business_hours(client):
    """Les horaires d'ouverture ne concernent que les appels ENTRANTS (télé-secrétariat), pas les sortants."""
    headers = setup_org(client)
    agent = create_agent_with_hours(client, headers, business_hours_start="03:00", business_hours_end="03:01")
    response = client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000", "direction": "outbound"},
        headers=headers,
    )
    assert response.json()["status"] != "message_taken"


def test_update_message_status(client):
    headers = setup_org(client)
    agent = create_agent_with_hours(client, headers, business_hours_start="03:00", business_hours_end="03:01")
    create_inbound_call(client, headers, agent["id"])
    message = client.get("/messages", headers=headers).json()[0]

    response = client.patch(f"/messages/{message['id']}", json={"status": "handled"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "handled"


def test_update_message_rejects_invalid_status(client):
    headers = setup_org(client)
    agent = create_agent_with_hours(client, headers, business_hours_start="03:00", business_hours_end="03:01")
    create_inbound_call(client, headers, agent["id"])
    message = client.get("/messages", headers=headers).json()[0]

    response = client.patch(f"/messages/{message['id']}", json={"status": "n_importe_quoi"}, headers=headers)
    assert response.status_code == 400


def test_messages_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    agent_a = create_agent_with_hours(client, headers_a, business_hours_start="03:00", business_hours_end="03:01")
    create_inbound_call(client, headers_a, agent_a["id"])

    messages_b = client.get("/messages", headers=headers_b).json()
    assert len(messages_b) == 0
