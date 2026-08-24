"""
Tests de l'appel de démo public (section 1/29 du cahier des charges) —
endpoint accessible sans compte, donc particulièrement sensible aux abus.
"""
from unittest.mock import patch

from tests.conftest import client


def test_demo_call_rejects_invalid_phone_format(client):
    response = client.post("/public/demo-call", json={"phone_number": "pas-un-numero"})
    assert response.status_code == 400


def test_demo_call_disabled_gracefully_when_not_configured(client):
    """Sans DEMO_AGENT_RETELL_ID/DEMO_FROM_NUMBER, la démo doit échouer proprement, pas planter."""
    with patch("app.api.routes.public_demo.settings") as mock_settings:
        mock_settings.demo_agent_retell_id = ""
        mock_settings.demo_from_number = ""
        response = client.post("/public/demo-call", json={"phone_number": "+221770000001"})
    assert response.status_code == 503


@patch("app.providers.voice.retell_provider.RetellProvider.create_phone_call")
def test_demo_call_succeeds_when_configured(mock_create_call, client):
    mock_create_call.return_value = {"call_id": "call_demo_fake"}
    with patch("app.api.routes.public_demo.settings") as mock_settings:
        mock_settings.demo_agent_retell_id = "agent_demo_fake"
        mock_settings.demo_from_number = "+15722204512"
        mock_settings.retell_api_key = "fake_key"
        response = client.post("/public/demo-call", json={"phone_number": "+221770000002"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_create_call.assert_called_once_with(to_number="+221770000002", from_number="+15722204512")


@patch("app.providers.voice.retell_provider.RetellProvider.create_phone_call")
def test_demo_call_daily_limit_enforced_per_phone_number(mock_create_call, client):
    """Test central du correctif anti-abus : un même numéro ne peut déclencher qu'un appel par jour."""
    mock_create_call.return_value = {"call_id": "call_demo_fake"}
    with patch("app.api.routes.public_demo.settings") as mock_settings:
        mock_settings.demo_agent_retell_id = "agent_demo_fake"
        mock_settings.demo_from_number = "+15722204512"
        mock_settings.retell_api_key = "fake_key"

        first = client.post("/public/demo-call", json={"phone_number": "+221770000003"})
        second = client.post("/public/demo-call", json={"phone_number": "+221770000003"})

    assert first.status_code == 200
    assert second.status_code == 429
    mock_create_call.assert_called_once()  # jamais appelé une deuxième fois


@patch("app.providers.voice.retell_provider.RetellProvider.create_phone_call")
def test_demo_call_limit_is_per_phone_not_global(mock_create_call, client):
    """Le plafond est bien PAR NUMÉRO — un autre numéro ne doit pas être bloqué par le premier."""
    mock_create_call.return_value = {"call_id": "call_demo_fake"}
    with patch("app.api.routes.public_demo.settings") as mock_settings:
        mock_settings.demo_agent_retell_id = "agent_demo_fake"
        mock_settings.demo_from_number = "+15722204512"
        mock_settings.retell_api_key = "fake_key"

        client.post("/public/demo-call", json={"phone_number": "+221770000004"})
        response = client.post("/public/demo-call", json={"phone_number": "+221770000005"})

    assert response.status_code == 200


def test_demo_call_handles_phone_with_spaces_and_dashes(client):
    """Cohérent avec l'import CSV et les autres endpoints : nettoie le format avant validation."""
    with patch("app.providers.voice.retell_provider.RetellProvider.create_phone_call") as mock_create_call:
        mock_create_call.return_value = {"call_id": "call_demo_fake"}
        with patch("app.api.routes.public_demo.settings") as mock_settings:
            mock_settings.demo_agent_retell_id = "agent_demo_fake"
            mock_settings.demo_from_number = "+15722204512"
            mock_settings.retell_api_key = "fake_key"
            response = client.post("/public/demo-call", json={"phone_number": "+221 77 000 00 06"})
    assert response.status_code == 200


@patch("app.providers.voice.retell_provider.RetellProvider.create_phone_call")
def test_demo_call_failure_from_retell_returns_clean_error_not_crash(mock_create_call, client):
    mock_create_call.side_effect = Exception("Retell API indisponible")
    with patch("app.api.routes.public_demo.settings") as mock_settings:
        mock_settings.demo_agent_retell_id = "agent_demo_fake"
        mock_settings.demo_from_number = "+15722204512"
        mock_settings.retell_api_key = "fake_key"
        response = client.post("/public/demo-call", json={"phone_number": "+221770000007"})
    assert response.status_code == 502
    assert "réessayez" in response.json()["detail"].lower()


def test_demo_call_endpoint_requires_no_authentication(client):
    """Confirme explicitement que cet endpoint est bien accessible sans JWT/organization_id — c'est voulu."""
    response = client.post("/public/demo-call", json={"phone_number": "invalide"})
    # 400 (validation) et non 401/403 (auth) — prouve qu'aucune authentification n'a été exigée avant la validation
    assert response.status_code == 400
