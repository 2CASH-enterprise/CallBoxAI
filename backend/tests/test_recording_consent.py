"""
Tests du consentement à l'enregistrement (section 42/43) : la personne peut
refuser d'être enregistrée tout en continuant l'appel — le contenu détaillé
n'est alors jamais conservé, seul le résultat de qualification l'est.
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


def test_withdraw_consent_tool_marks_call_when_found(client, db_session):
    headers = setup_org(client)
    _setup_agent_with_retell_id(client, db_session, headers, "retell_consent_001")

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_consent_001", "agent_id": "retell_consent_001", "direction": "inbound", "from_number": "+33612970001"},
    })

    response = client.post(
        "/webhooks/retell/tools/withdraw-recording-consent",
        json={"name": "withdraw_recording_consent", "call": {"call_id": "call_consent_001"}, "args": {}},
    )
    assert response.status_code == 200
    assert "continue" in response.json()["result"].lower()

    from app.models.call import Call
    call = db_session.query(Call).filter(Call.provider_call_id == "call_consent_001").first()
    assert call.recording_consent_refused is True


def test_withdraw_consent_tool_never_crashes_when_call_not_found(client):
    """Résilience (section 29) : jamais d'erreur qui interromprait la conversation."""
    response = client.post(
        "/webhooks/retell/tools/withdraw-recording-consent",
        json={"name": "withdraw_recording_consent", "call": {"call_id": "call_inexistant"}, "args": {}},
    )
    assert response.status_code == 200


def test_withdraw_consent_tool_never_crashes_without_call_object(client):
    response = client.post(
        "/webhooks/retell/tools/withdraw-recording-consent",
        json={"name": "withdraw_recording_consent", "args": {}},
    )
    assert response.status_code == 200


def test_transcript_redacted_when_consent_refused(client, db_session):
    """Test central : contenu détaillé purgé, mais classification bien effectuée."""
    headers = setup_org(client)
    _setup_agent_with_retell_id(client, db_session, headers, "retell_consent_002")

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_consent_002", "agent_id": "retell_consent_002", "direction": "inbound", "from_number": "+33612970002"},
    })

    # L'interlocuteur retire son consentement en cours d'appel
    client.post(
        "/webhooks/retell/tools/withdraw-recording-consent",
        json={"name": "withdraw_recording_consent", "call": {"call_id": "call_consent_002"}, "args": {}},
    )

    client.post("/webhooks/retell", json={
        "event": "call_analyzed",
        "call": {
            "call_id": "call_consent_002", "agent_id": "retell_consent_002",
            "transcript": "Client: Je suis très intéressé par votre offre, contactez-moi vite !",
            "call_analysis": {"call_summary": "Client très intéressé, souhaite être recontacté rapidement."},
        },
    })

    headers2 = headers
    calls = client.get("/calls", headers=headers2).json()
    call = calls[0]  # un seul appel dans ce test

    assert "Non conservé" in call["transcript"]
    assert "Non conservé" in call["summary"]
    # La classification, elle, a bien eu lieu à partir du VRAI contenu
    assert call["qualification"] is not None


def test_transcript_preserved_when_consent_not_refused(client, db_session):
    headers = setup_org(client)
    _setup_agent_with_retell_id(client, db_session, headers, "retell_consent_003")

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_consent_003", "agent_id": "retell_consent_003", "direction": "inbound", "from_number": "+33612970003"},
    })
    client.post("/webhooks/retell", json={
        "event": "call_analyzed",
        "call": {
            "call_id": "call_consent_003", "agent_id": "retell_consent_003",
            "transcript": "Client: Tout va bien, merci.",
            "call_analysis": {"call_summary": "Appel de courtoisie."},
        },
    })

    calls = client.get("/calls", headers=headers).json()
    call = calls[0]
    assert "Non conservé" not in call["transcript"]
    assert call["transcript"] == "Client: Tout va bien, merci."
