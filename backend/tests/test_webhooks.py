"""
Tests des webhooks Retell/Twilio (section 30 du cahier des charges).
Ces endpoints ne sont pas protégés par JWT (Retell/Twilio nous appellent
directement) — testés ici avec des payloads simulés, sans vrai compte.
"""
from tests.conftest import auth_headers, register_user


def setup_call(client):
    """Crée un appel Mock, dont le provider_call_id servira à simuler un webhook."""
    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}
    agent = client.post("/agents", json={"name": "Agent webhook"}, headers=headers).json()
    call = client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers,
    ).json()
    return headers, call


def test_retell_webhook_updates_call_transcript_and_summary(client):
    headers, call = setup_call(client)

    response = client.post(
        "/webhooks/retell",
        json={
            "event": "call_ended",
            "call": {
                "call_id": call["provider_call_id"],
                "transcript": "Agent: Vrai transcript reçu via webhook.",
                "call_analysis": {"call_summary": "Résumé reçu via webhook Retell."},
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    updated = client.get("/calls", headers=headers).json()[0]
    assert updated["transcript"] == "Agent: Vrai transcript reçu via webhook."
    assert updated["summary"] == "Résumé reçu via webhook Retell."


def test_retell_webhook_ignores_unknown_call(client):
    response = client.post(
        "/webhooks/retell",
        json={"event": "call_ended", "call": {"call_id": "id-qui-nexiste-pas"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_twilio_webhook_updates_call_status(client):
    headers, call = setup_call(client)

    response = client.post(
        "/webhooks/twilio",
        data={"CallSid": call["provider_call_id"], "CallStatus": "failed"},
    )
    assert response.status_code == 200

    updated = client.get("/calls", headers=headers).json()[0]
    assert updated["status"] == "failed"


def test_twilio_webhook_ignores_unknown_call(client):
    response = client.post("/webhooks/twilio", data={"CallSid": "CAinconnu", "CallStatus": "completed"})
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
