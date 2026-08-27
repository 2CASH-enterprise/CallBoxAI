"""
Tests de la capture de la durée réelle des appels (section 40 — nécessaire
à la facturation à la minute des agents accueil/support). Retell transmet
cette donnée dans le webhook call_ended, jamais exploitée jusqu'ici.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def _setup_agent_with_retell_id(client, db_session, headers, retell_agent_id):
    from app.models.agent import Agent
    import uuid as uuid_module

    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.retell_agent_id = retell_agent_id
    db_session.commit()
    return agent


def test_duration_captured_from_duration_ms_field(client, db_session):
    headers = setup_org(client)
    _setup_agent_with_retell_id(client, db_session, headers, "retell_duration_test_001")

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_duration_001", "agent_id": "retell_duration_test_001", "direction": "inbound", "from_number": "+33612800001"},
    })
    client.post("/webhooks/retell", json={
        "event": "call_ended",
        "call": {"call_id": "call_duration_001", "agent_id": "retell_duration_test_001", "duration_ms": 125000},
    })

    calls = client.get("/calls", headers=headers).json()
    assert calls[0]["duration_seconds"] == 125


def test_duration_computed_from_start_end_timestamps_when_duration_ms_absent(client, db_session):
    headers = setup_org(client)
    _setup_agent_with_retell_id(client, db_session, headers, "retell_duration_test_002")

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_duration_002", "agent_id": "retell_duration_test_002", "direction": "inbound", "from_number": "+33612800002"},
    })
    client.post("/webhooks/retell", json={
        "event": "call_ended",
        "call": {"call_id": "call_duration_002", "agent_id": "retell_duration_test_002", "start_timestamp": 1714608475945, "end_timestamp": 1714608491736},
    })

    calls = client.get("/calls", headers=headers).json()
    assert calls[0]["duration_seconds"] == 16  # (491736 - 475945) / 1000, arrondi


def test_duration_stays_zero_gracefully_when_no_duration_data_available(client, db_session):
    """Résilience (section 29) : sans donnée de durée, ne jamais planter, juste rester à 0."""
    headers = setup_org(client)
    _setup_agent_with_retell_id(client, db_session, headers, "retell_duration_test_003")

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_duration_003", "agent_id": "retell_duration_test_003", "direction": "inbound", "from_number": "+33612800003"},
    })
    response = client.post("/webhooks/retell", json={
        "event": "call_ended",
        "call": {"call_id": "call_duration_003", "agent_id": "retell_duration_test_003"},
    })

    assert response.status_code == 200
    calls = client.get("/calls", headers=headers).json()
    assert calls[0]["duration_seconds"] == 0
