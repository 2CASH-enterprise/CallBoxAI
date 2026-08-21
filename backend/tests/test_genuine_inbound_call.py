"""
Tests d'un VRAI appel entrant, jamais déclenché par notre dashboard (ni
"Simuler un appel", ni "Tester en direct") — reproduit exactement le
scénario où quelqu'un compose directement le numéro connecté à l'agent
(section 16/30 du cahier des charges).
"""
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_genuine_inbound_call_creates_call_from_scratch(client, db_session):
    """
    Test central du correctif : un appel dont on n'a JAMAIS entendu parler
    (aucune ligne Call préexistante) doit être créé par le webhook lui-même,
    à partir du seul agent_id Retell transmis dans le payload.
    """
    headers = setup_org(client)
    agent = client.post(
        "/agents", json={"name": "Réceptionniste"}, headers=headers
    ).json()

    # Simule le rattachement Retell (normalement fait par le provisionnement réel)
    from app.models.agent import Agent
    import uuid as uuid_module

    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.retell_agent_id = "retell_agent_reel_001"
    db_session.commit()

    # Aucun appel n'existe encore côté CallBoxAI — c'est le premier événement reçu
    response = client.post(
        "/webhooks/retell",
        json={
            "event": "call_started",
            "call": {
                "call_id": "call_inbound_reel_001",
                "agent_id": "retell_agent_reel_001",
                "direction": "inbound",
                "from_number": "+33612390001",
                "to_number": "+15722204512",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    calls = client.get("/calls", headers=headers).json()
    assert len(calls) == 1
    assert calls[0]["provider_call_id"] == "call_inbound_reel_001"
    assert calls[0]["direction"] == "inbound"

    # Le contact appelant doit avoir été créé automatiquement, par téléphone
    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["phone"] == "+33612390001"


def test_genuine_inbound_call_completes_with_classification_and_ticket(client, db_session):
    """Le cycle complet : appel jamais initié par nous, jusqu'à la classification et le ticket."""
    headers = setup_org(client)
    agent = client.post(
        "/agents", json={"name": "Réceptionniste", "ticketing_enabled": True}, headers=headers
    ).json()

    from app.models.agent import Agent
    import uuid as uuid_module

    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.retell_agent_id = "retell_agent_reel_002"
    db_session.commit()

    call_data = {
        "call_id": "call_inbound_reel_002",
        "agent_id": "retell_agent_reel_002",
        "direction": "inbound",
        "from_number": "+33612390002",
        "to_number": "+15722204512",
    }

    client.post("/webhooks/retell", json={"event": "call_started", "call": call_data})
    client.post("/webhooks/retell", json={
        "event": "call_ended",
        "call": {**call_data, "transcript": "Agent: Bonjour. Client: J'ai une question."},
    })
    client.post("/webhooks/retell", json={
        "event": "call_analyzed",
        "call": {**call_data, "transcript": "Agent: Bonjour. Client: J'ai une question.", "call_analysis": {"call_summary": "Question générale."}},
    })

    calls = client.get("/calls", headers=headers).json()
    assert calls[0]["status"] == "completed"
    assert calls[0]["intent"] is not None

    tickets = client.get("/tickets", headers=headers).json()
    assert len(tickets) == 1


def test_genuine_inbound_call_reuses_existing_contact_by_phone(client, db_session):
    """Si l'appelant est déjà connu (même numéro), pas de doublon créé."""
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Réceptionniste"}, headers=headers).json()
    client.post("/contacts", json={"phone": "+33612390003", "first_name": "Déjà là"}, headers=headers)

    from app.models.agent import Agent
    import uuid as uuid_module

    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.retell_agent_id = "retell_agent_reel_003"
    db_session.commit()

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_inbound_reel_003", "agent_id": "retell_agent_reel_003", "direction": "inbound", "from_number": "+33612390003"},
    })

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["first_name"] == "Déjà là"


def test_webhook_ignores_unknown_retell_agent_gracefully(client):
    """Un agent_id Retell qu'on ne reconnaît pas (autre compte, erreur) ne doit jamais planter."""
    response = client.post(
        "/webhooks/retell",
        json={"event": "call_started", "call": {"call_id": "call_x", "agent_id": "agent_totalement_inconnu"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_genuine_inbound_calls_isolated_between_organizations(client, db_session):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    agent_a = client.post("/agents", json={"name": "Agent A"}, headers=headers_a).json()

    from app.models.agent import Agent
    import uuid as uuid_module

    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent_a["id"])).first()
    db_agent.retell_agent_id = "retell_agent_reel_004"
    db_session.commit()

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_inbound_reel_004", "agent_id": "retell_agent_reel_004", "direction": "inbound", "from_number": "+33612390004"},
    })

    calls_b = client.get("/calls", headers=headers_b).json()
    assert len(calls_b) == 0
