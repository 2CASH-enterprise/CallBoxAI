"""
Tests du cas d'usage Service Client : tickets automatiques pour les appels
entrants (sections 1 et 12 du cahier des charges).
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent(client, headers, ticketing_enabled=True, **overrides):
    payload = {"name": "Agent Service Client", "ticketing_enabled": ticketing_enabled}
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def create_inbound_call(client, headers, agent_id, contact_id=None):
    body = {"agent_id": agent_id, "to_number": "+221780000000", "from_number": "+221770000000", "direction": "inbound"}
    if contact_id:
        body["contact_id"] = contact_id
    return client.post("/calls", json=body, headers=headers)


def test_ticket_auto_created_for_inbound_call_when_enabled(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, ticketing_enabled=True)
    response = create_inbound_call(client, headers, agent["id"])
    assert response.status_code == 200

    tickets = client.get("/tickets", headers=headers).json()
    assert len(tickets) == 1
    assert tickets[0]["status"] == "ouvert"
    assert tickets[0]["priority"] in ("basse", "normale", "haute")
    assert tickets[0]["category"] is not None  # repris de l'intent de la classification


def test_no_ticket_when_ticketing_disabled(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, ticketing_enabled=False)
    create_inbound_call(client, headers, agent["id"])

    tickets = client.get("/tickets", headers=headers).json()
    assert len(tickets) == 0


def test_no_ticket_for_outbound_calls_even_when_enabled(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, ticketing_enabled=True)
    client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000", "direction": "outbound"},
        headers=headers,
    )
    tickets = client.get("/tickets", headers=headers).json()
    assert len(tickets) == 0


def test_no_ticket_when_call_diverted_to_message_taking(client):
    """Hors horaires, l'appel devient un Message (télé-secrétariat), pas un ticket, même si ticketing_enabled=True."""
    headers = setup_org(client)
    agent = create_agent(
        client, headers, ticketing_enabled=True, business_hours_start="03:00", business_hours_end="03:01"
    )
    create_inbound_call(client, headers, agent["id"])

    assert len(client.get("/tickets", headers=headers).json()) == 0
    assert len(client.get("/messages", headers=headers).json()) == 1


def test_ticket_links_to_contact_and_call(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    contact = client.post("/contacts", json={"phone": "+221770000001"}, headers=headers).json()
    call = create_inbound_call(client, headers, agent["id"], contact_id=contact["id"]).json()

    ticket = client.get("/tickets", headers=headers).json()[0]
    assert ticket["contact_id"] == contact["id"]
    assert ticket["call_id"] == call["id"]


def test_update_ticket_status_and_resolution(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    create_inbound_call(client, headers, agent["id"])
    ticket = client.get("/tickets", headers=headers).json()[0]

    response = client.patch(
        f"/tickets/{ticket['id']}",
        json={"status": "résolu", "resolution_notes": "Problème réglé par téléphone."},
        headers=headers,
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "résolu"
    assert updated["resolution_notes"] == "Problème réglé par téléphone."


def test_update_ticket_rejects_invalid_status(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    create_inbound_call(client, headers, agent["id"])
    ticket = client.get("/tickets", headers=headers).json()[0]

    response = client.patch(f"/tickets/{ticket['id']}", json={"status": "n_importe_quoi"}, headers=headers)
    assert response.status_code == 400


def test_update_ticket_rejects_invalid_priority(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    create_inbound_call(client, headers, agent["id"])
    ticket = client.get("/tickets", headers=headers).json()[0]

    response = client.patch(f"/tickets/{ticket['id']}", json={"priority": "n_importe_quoi"}, headers=headers)
    assert response.status_code == 400


def test_tickets_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    agent_a = create_agent(client, headers_a)
    create_inbound_call(client, headers_a, agent_a["id"])

    tickets_b = client.get("/tickets", headers=headers_b).json()
    assert len(tickets_b) == 0


def test_cannot_update_ticket_from_another_organization(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    agent_a = create_agent(client, headers_a)
    create_inbound_call(client, headers_a, agent_a["id"])
    ticket = client.get("/tickets", headers=headers_a).json()[0]

    response = client.patch(f"/tickets/{ticket['id']}", json={"status": "fermé"}, headers=headers_b)
    assert response.status_code == 404
