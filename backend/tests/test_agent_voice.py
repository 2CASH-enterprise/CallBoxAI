"""
Tests du choix de voix par agent (section 16 du cahier des charges).
"""
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_agent_stores_custom_voice_id(client):
    headers = setup_org(client)
    response = client.post(
        "/agents", json={"name": "Agent test", "voice_id": "11labs-Charlotte"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["voice_id"] == "11labs-Charlotte"


@patch("app.providers.voice.retell_provider.RetellProvider.provision_agent")
def test_custom_voice_id_used_during_provisioning(mock_provision, client):
    mock_provision.return_value = {"agent_id": "agent_fake_123", "llm_id": "llm_fake_123"}
    headers = setup_org(client)

    with patch("app.api.routes.agents.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        mock_settings.retell_default_llm_model = "gpt-4o-mini"
        mock_settings.retell_default_voice_id = "retell-Cimo"

        client.post(
            "/agents", json={"name": "Agent test", "voice_id": "11labs-Charlotte"}, headers=headers
        )

    _, kwargs = mock_provision.call_args
    assert kwargs["voice_id"] == "11labs-Charlotte"  # pas la voix par défaut


@patch("app.providers.voice.retell_provider.RetellProvider.provision_agent")
def test_falls_back_to_default_voice_when_not_specified(mock_provision, client):
    mock_provision.return_value = {"agent_id": "agent_fake_123", "llm_id": "llm_fake_123"}
    headers = setup_org(client)

    with patch("app.api.routes.agents.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        mock_settings.retell_default_llm_model = "gpt-4o-mini"
        mock_settings.retell_default_voice_id = "retell-Cimo"

        client.post("/agents", json={"name": "Agent sans voix précisée"}, headers=headers)

    _, kwargs = mock_provision.call_args
    assert kwargs["voice_id"] == "retell-Cimo"


@patch("app.providers.voice.retell_provider.RetellProvider.provision_agent")
def test_update_voice_id_triggers_reprovisioning(mock_provision, client):
    mock_provision.side_effect = [{"agent_id": "agent_v1", "llm_id": "llm_v1"}, {"agent_id": "agent_v2", "llm_id": "llm_v2"}]
    headers = setup_org(client)

    with patch("app.api.routes.agents.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        mock_settings.retell_default_llm_model = "gpt-4o-mini"
        mock_settings.retell_default_voice_id = "retell-Cimo"

        agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
        assert agent["retell_agent_id"] == "agent_v1"

        updated = client.patch(
            f"/agents/{agent['id']}", json={"voice_id": "11labs-Charlotte"}, headers=headers
        ).json()

    assert updated["voice_id"] == "11labs-Charlotte"
    assert updated["retell_agent_id"] == "agent_v2"  # re-provisionné avec la nouvelle voix


def test_update_agent_without_voice_change_does_not_reprovision(client):
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    # Sans Retell configuré (mode Mock par défaut) : pas d'erreur, juste une
    # mise à jour normale du champ transfer_enabled.
    updated = client.patch(f"/agents/{agent['id']}", json={"transfer_enabled": True}, headers=headers).json()
    assert updated["transfer_enabled"] is True
    assert updated["retell_agent_id"] is None


def test_update_agent_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    agent_a = client.post("/agents", json={"name": "Agent A"}, headers=headers_a).json()

    response = client.patch(f"/agents/{agent_a['id']}", json={"name": "Hack"}, headers=headers_b)
    assert response.status_code == 404


@patch("app.providers.voice.retell_provider.RetellProvider.update_agent")
@patch("app.providers.voice.retell_provider.RetellProvider.update_llm")
@patch("app.providers.voice.retell_provider.RetellProvider.publish_agent")
def test_update_voice_id_reuses_same_retell_agent_no_duplicate(mock_publish, mock_update_llm, mock_update_agent, client):
    """
    Test central du correctif : modifier un agent doit RÉUTILISER l'agent
    Retell existant (update-agent/update-retell-llm), jamais en créer un
    nouveau — c'est ce qui causait l'accumulation de doublons chez Retell.
    """
    headers = setup_org(client)

    with patch("app.providers.voice.retell_provider.RetellProvider.create_llm") as mock_create_llm, \
         patch("app.providers.voice.retell_provider.RetellProvider.create_retell_agent") as mock_create_agent:
        mock_create_llm.return_value = {"llm_id": "llm_original"}
        mock_create_agent.return_value = {"agent_id": "agent_original"}

        with patch("app.api.routes.agents.settings") as mock_settings:
            mock_settings.voice_provider = "retell"
            mock_settings.retell_api_key = "fake_key"
            mock_settings.retell_default_llm_model = "gpt-4o-mini"
            mock_settings.retell_default_voice_id = "cartesia-Emma"
            mock_settings.public_base_url = ""

            agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

        assert agent["retell_agent_id"] == "agent_original"
        mock_create_llm.assert_called_once()  # création une seule fois, à l'origine

        # Modification : ne doit PAS rappeler create_llm/create_retell_agent
        with patch("app.api.routes.agents.settings") as mock_settings:
            mock_settings.voice_provider = "retell"
            mock_settings.retell_api_key = "fake_key"
            mock_settings.retell_default_llm_model = "gpt-4o-mini"
            mock_settings.retell_default_voice_id = "cartesia-Emma"
            mock_settings.public_base_url = ""

            updated = client.patch(
                f"/agents/{agent['id']}", json={"voice_id": "11labs-Charlotte"}, headers=headers
            ).json()

        # Toujours le MÊME agent_id Retell — pas de doublon créé
        assert updated["retell_agent_id"] == "agent_original"
        mock_create_llm.assert_called_once()  # toujours une seule fois
        mock_create_agent.assert_called_once()  # toujours une seule fois
        mock_update_llm.assert_called_once_with(
            "llm_original", general_prompt="Tu es Agent test, un assistant vocal utile.", model="gpt-4o-mini", tools=None
        )
        mock_update_agent.assert_called_once()
        _, update_agent_kwargs = mock_update_agent.call_args
        assert update_agent_kwargs["llm_id"] == "llm_original"
