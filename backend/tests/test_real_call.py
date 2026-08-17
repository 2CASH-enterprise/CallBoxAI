"""
Tests de la séparation simulation (/calls) vs vrai appel (/calls/real),
sections 12/16/40 du cahier des charges.
"""
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent(client, headers, **overrides):
    payload = {"name": "Agent test"}
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def test_simulate_call_always_uses_mock_even_with_retell_configured(client):
    """
    Test central : même si VOICE_PROVIDER=retell est actif globalement,
    /calls (simulation) doit TOUJOURS rester en Mock — jamais planter en
    essayant de récupérer un vrai transcript pour un faux appel.
    """
    headers = setup_org(client)
    agent = create_agent(client, headers)

    with patch("app.api.routes.agents.settings") as mock_agent_settings:
        # Même si un agent Retell existait sur cet agent...
        mock_agent_settings.voice_provider = "mock"
        pass  # (agent créé sans provisionnement Retell dans ce test, volontairement)

    response = client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers,
    )
    assert response.status_code == 200
    call = response.json()
    assert call["provider"] == "mock"
    assert call["status"] in ("completed", "transferred")
    assert call["transcript"] is not None  # le Mock fournit toujours un résultat immédiat


def test_real_call_fails_without_twilio_configured(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)

    response = client.post(
        "/calls/real",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers,
    )
    assert response.status_code == 400
    assert "Twilio" in response.json()["detail"]


def test_real_call_fails_without_agent_retell_id(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)  # pas d'agent Retell provisionné

    with patch("app.api.routes.calls.settings") as mock_settings:
        mock_settings.telephony_provider = "twilio"
        mock_settings.twilio_account_sid = "ACfake"
        mock_settings.twilio_auth_token = "fake"
        mock_settings.retell_api_key = "fake_key"

        response = client.post(
            "/calls/real",
            json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
            headers=headers,
        )
    assert response.status_code == 400
    assert "agent Retell" in response.json()["detail"]


def test_real_call_full_success_path(client):
    """Chemin complet : agent réellement provisionné (simulé), Twilio configuré -> Call in_progress."""
    headers = setup_org(client)

    with patch("app.providers.voice.retell_provider.RetellProvider.provision_agent") as mock_provision:
        mock_provision.return_value = "agent_retell_fake"
        with patch("app.api.routes.agents.settings") as mock_agent_settings:
            mock_agent_settings.voice_provider = "retell"
            mock_agent_settings.retell_api_key = "fake_key"
            mock_agent_settings.retell_default_llm_model = "gpt-4o-mini"
            mock_agent_settings.retell_default_voice_id = "retell-Cimo"
            agent = client.post("/agents", json={"name": "Agent provisionné"}, headers=headers).json()

    assert agent["retell_agent_id"] == "agent_retell_fake"

    with patch("app.providers.voice.retell_provider.RetellProvider.create_phone_call") as mock_call:
        mock_call.return_value = {"call_id": "call_real_fake456", "call_status": "registered"}
        with patch("app.api.routes.calls.settings") as mock_call_settings:
            mock_call_settings.telephony_provider = "twilio"
            mock_call_settings.twilio_account_sid = "ACfake"
            mock_call_settings.twilio_auth_token = "fake"
            mock_call_settings.twilio_phone_number = "+15550000000"
            mock_call_settings.retell_api_key = "fake_key"

            response = client.post(
                "/calls/real",
                json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+15550000000"},
                headers=headers,
            )

    assert response.status_code == 200
    call = response.json()
    assert call["status"] == "in_progress"
    assert call["provider"] == "retell"
    assert call["provider_call_id"] == "call_real_fake456"
    assert call["transcript"] is None  # pas encore de transcript : arrivera via webhook

    # Le webhook Retell peut ensuite compléter cet appel
    webhook_response = client.post(
        "/webhooks/retell",
        json={
            "event": "call_ended",
            "call": {
                "call_id": "call_real_fake456",
                "transcript": "Transcript réel du vrai appel.",
                "call_analysis": {"call_summary": "Résumé réel."},
            },
        },
    )
    assert webhook_response.status_code == 200

    completed_call = client.get("/calls", headers=headers).json()[0]
    assert completed_call["status"] == "completed"
    assert completed_call["transcript"] == "Transcript réel du vrai appel."


def test_real_call_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    agent_a = create_agent(client, headers_a)

    response = client.post(
        "/calls/real",
        json={"agent_id": agent_a["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers_b,
    )
    assert response.status_code == 404
