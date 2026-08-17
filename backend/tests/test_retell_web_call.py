"""
Tests du test vocal en direct (Web Call Retell, section 16) — sans jamais
appeler la vraie API Retell (mock HTTP).
"""
from unittest.mock import MagicMock, patch

from tests.conftest import auth_headers, register_user


def setup_agent(client, **overrides):
    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}
    payload = {"name": "Agent testable"}
    payload.update(overrides)
    agent = client.post("/agents", json=payload, headers=headers).json()
    return headers, agent


def test_test_call_fails_without_retell_api_key(client):
    headers, agent = setup_agent(client, retell_agent_id="retell-agent-fake")
    # Par défaut en tests, RETELL_API_KEY est vide (mode Mock)
    response = client.post(f"/agents/{agent['id']}/test-call", headers=headers)
    assert response.status_code == 400
    assert "RETELL_API_KEY" in response.json()["detail"]


def test_test_call_fails_without_any_retell_agent_id(client):
    headers, agent = setup_agent(client)  # pas de retell_agent_id
    with patch("app.api.routes.agents.settings") as mock_settings:
        mock_settings.retell_api_key = "fake_key"
        mock_settings.retell_agent_id = ""  # pas de fallback global non plus
        response = client.post(f"/agents/{agent['id']}/test-call", headers=headers)
    assert response.status_code == 400
    assert "agent Retell" in response.json()["detail"]


@patch("app.providers.voice.retell_provider.RetellProvider.create_web_call")
def test_test_call_succeeds_with_configuration(mock_create_web_call, client):
    headers, agent = setup_agent(client, retell_agent_id="retell-agent-fake")
    mock_create_web_call.return_value = {"access_token": "fake_token_abc", "call_id": "call_fake123"}

    with patch("app.api.routes.agents.settings") as mock_settings:
        mock_settings.retell_api_key = "fake_key"
        mock_settings.retell_agent_id = ""
        response = client.post(f"/agents/{agent['id']}/test-call", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "fake_token_abc"
    assert body["call_id"] == "call_fake123"


def test_test_call_isolated_between_organizations(client):
    headers_a, agent_a = setup_agent(client, retell_agent_id="retell-agent-fake")
    token_b, org_b_id = register_user(client, org_name="Entreprise B")
    headers_b = {**auth_headers(token_b), "x-organization-id": org_b_id}

    response = client.post(f"/agents/{agent_a['id']}/test-call", headers=headers_b)
    assert response.status_code == 404
