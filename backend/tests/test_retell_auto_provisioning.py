"""
Tests du provisionnement automatique d'agent Retell (section 16 du cahier
des charges) — sans jamais appeler la vraie API. Vérifie surtout la
résilience : Retell mal configuré ou en panne ne doit JAMAIS empêcher la
création d'un agent CallBoxAI (section 29).
"""
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def test_agent_creation_succeeds_without_retell_configured(client):
    """Comportement par défaut (mode Mock) : la création fonctionne, sans agent Retell."""
    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}

    response = client.post("/agents", json={"name": "Agent simple"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["retell_agent_id"] is None


@patch("app.providers.voice.retell_provider.RetellProvider.provision_agent")
def test_agent_creation_auto_provisions_retell_agent_when_configured(mock_provision, client):
    mock_provision.return_value = {"agent_id": "agent_fake_provisioned_123", "llm_id": "llm_fake_123"}
    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}

    with patch("app.api.routes.agents.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        mock_settings.retell_default_llm_model = "gpt-4o-mini"
        mock_settings.retell_default_voice_id = "retell-Cimo"

        response = client.post(
            "/agents",
            json={"name": "Agent commercial", "system_prompt": "Tu es un agent commercial.", "language": "fr"},
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["retell_agent_id"] == "agent_fake_provisioned_123"

    mock_provision.assert_called_once()
    _, kwargs = mock_provision.call_args
    assert kwargs["name"] == "Agent commercial"
    assert kwargs["system_prompt"] == "Tu es un agent commercial."


@patch("app.providers.voice.retell_provider.RetellProvider.provision_agent")
def test_agent_creation_resilient_to_retell_failure(mock_provision, client):
    """
    Critique (section 29) : si Retell échoue (panne, quota dépassé, clé
    invalide...), la création de l'agent CallBoxAI doit quand même réussir.
    """
    mock_provision.side_effect = Exception("Retell API indisponible (simulation)")
    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}

    with patch("app.api.routes.agents.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        mock_settings.retell_default_llm_model = "gpt-4o-mini"
        mock_settings.retell_default_voice_id = "retell-Cimo"

        response = client.post("/agents", json={"name": "Agent résilient"}, headers=headers)

    assert response.status_code == 200  # l'agent CallBoxAI existe quand même
    assert response.json()["retell_agent_id"] is None  # mais sans agent Retell


@patch("httpx.Client.post")
def test_retell_provider_provision_agent_orchestrates_correctly(mock_post):
    """Vérifie l'enchaînement create-retell-llm -> create-agent -> publish-agent."""
    from app.providers.voice.retell_provider import RetellProvider
    from unittest.mock import MagicMock

    llm_response = MagicMock()
    llm_response.json.return_value = {"llm_id": "llm_fake123"}
    llm_response.raise_for_status.return_value = None

    agent_response = MagicMock()
    agent_response.json.return_value = {"agent_id": "agent_fake456", "is_published": False}
    agent_response.raise_for_status.return_value = None

    publish_response = MagicMock()
    publish_response.json.return_value = {"agent_id": "agent_fake456", "is_published": True}
    publish_response.raise_for_status.return_value = None

    mock_post.side_effect = [llm_response, agent_response, publish_response]

    provider = RetellProvider(api_key="fake_key", agent_id="")
    result = provider.provision_agent(
        name="Agent test", system_prompt="Prompt de test", language="fr",
        model="gpt-4o-mini", voice_id="retell-Cimo",
    )

    assert result["agent_id"] == "agent_fake456"
    assert result["llm_id"] == "llm_fake123"
    assert mock_post.call_count == 3

    llm_call = mock_post.call_args_list[0]
    assert llm_call[0][0] == "/create-retell-llm"
    assert llm_call[1]["json"]["general_prompt"] == "Prompt de test"

    agent_call = mock_post.call_args_list[1]
    assert agent_call[0][0] == "/create-agent"
    assert agent_call[1]["json"]["response_engine"]["llm_id"] == "llm_fake123"
    assert agent_call[1]["json"]["voice_id"] == "retell-Cimo"

    publish_call = mock_post.call_args_list[2]
    assert publish_call[0][0] == "/publish-agent/agent_fake456"


@patch("httpx.Client.post")
def test_retell_provider_provision_agent_handles_empty_publish_response(mock_post):
    """
    Reproduit le bug réel rencontré en production : /publish-agent renvoie
    parfois un corps vide, ce qui ne doit jamais faire planter le
    provisionnement (l'agent_id est déjà connu à ce stade).
    """
    from unittest.mock import MagicMock
    from app.providers.voice.retell_provider import RetellProvider

    llm_response = MagicMock()
    llm_response.json.return_value = {"llm_id": "llm_fake123"}
    llm_response.raise_for_status.return_value = None

    agent_response = MagicMock()
    agent_response.json.return_value = {"agent_id": "agent_fake456", "is_published": False}
    agent_response.raise_for_status.return_value = None

    publish_response = MagicMock()
    publish_response.raise_for_status.return_value = None
    publish_response.content = b""  # corps vide, comme observé en réel

    mock_post.side_effect = [llm_response, agent_response, publish_response]

    provider = RetellProvider(api_key="fake_key", agent_id="")
    result = provider.provision_agent(
        name="Agent test", system_prompt="Prompt", language="fr",
        model="gpt-4o-mini", voice_id="retell-Cimo",
    )

    assert result["agent_id"] == "agent_fake456"  # ne plante pas, retourne bien l'agent_id
