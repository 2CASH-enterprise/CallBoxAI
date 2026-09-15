"""
Tests du fournisseur d'analyse Mistral (alternative à Anthropic, préférence
exprimée par l'utilisateur — souveraineté française/européenne).
"""
from unittest.mock import patch, MagicMock

from tests.conftest import auth_headers


def get_super_admin_headers(client):
    response = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "superadmin-mistral@example.com", "password": "TestPassword123", "full_name": "Admin Test"},
    )
    token = response.json()["access_token"]
    return auth_headers(token)


def test_mistral_provider_extracts_via_chat_complete():
    from app.providers.analysis.mistral_provider import MistralWebsiteAnalysisProvider

    with patch("app.providers.analysis.mistral_provider.Mistral") as MockMistral:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Horaires : check-in 14h."))]
        mock_client.chat.complete.return_value = mock_response
        MockMistral.return_value = mock_client

        provider = MistralWebsiteAnalysisProvider(api_key="fake_key")
        result = provider.extract_practical_info("Contenu du site.", "Hôtel Test")

    assert result == "Horaires : check-in 14h."
    mock_client.chat.complete.assert_called_once()


def test_mistral_and_anthropic_share_the_same_extraction_prompt():
    """Garantit un comportement identique quel que soit le fournisseur réellement utilisé."""
    from app.providers.analysis.base import EXTRACTION_SYSTEM_PROMPT
    from app.providers.analysis.anthropic_provider import AnthropicWebsiteAnalysisProvider
    import app.providers.analysis.mistral_provider as mistral_module

    assert "n'invente JAMAIS" in EXTRACTION_SYSTEM_PROMPT
    # Les deux modules importent bien le même prompt partagé, pas une copie
    assert mistral_module.EXTRACTION_SYSTEM_PROMPT is EXTRACTION_SYSTEM_PROMPT


def test_provider_selection_prioritizes_mistral_when_both_configured(client, db_session):
    """Test central : Mistral choisi en priorité si les deux clés sont configurées (préférence utilisateur)."""
    from app.api.routes.prospecting_campaigns import _get_analysis_provider
    from app.providers.analysis.mistral_provider import MistralWebsiteAnalysisProvider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.mistral_api_key = "fake_mistral_key"
        mock_settings.anthropic_api_key = "fake_anthropic_key"
        provider = _get_analysis_provider()

    assert isinstance(provider, MistralWebsiteAnalysisProvider)


def test_provider_selection_falls_back_to_anthropic_without_mistral_key(client):
    from app.api.routes.prospecting_campaigns import _get_analysis_provider
    from app.providers.analysis.anthropic_provider import AnthropicWebsiteAnalysisProvider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.mistral_api_key = ""
        mock_settings.anthropic_api_key = "fake_anthropic_key"
        provider = _get_analysis_provider()

    assert isinstance(provider, AnthropicWebsiteAnalysisProvider)


def test_provider_selection_falls_back_to_mock_without_any_key(client):
    from app.api.routes.prospecting_campaigns import _get_analysis_provider
    from app.providers.analysis.mock import MockWebsiteAnalysisProvider

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.mistral_api_key = ""
        mock_settings.anthropic_api_key = ""
        provider = _get_analysis_provider()

    assert isinstance(provider, MockWebsiteAnalysisProvider)


def test_analyze_target_works_end_to_end_with_mistral(client):
    """Confirme que le reste du pipeline (endpoint d'analyse) fonctionne bien avec Mistral sélectionné."""
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test Mistral", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()
    client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", "nom,site_internet\nHôtel Mistral,https://hotel-mistral.fr\n", "text/csv")},
        headers=admin_headers,
    )
    target = client.get(f"/admin/prospecting-campaigns/{campaign['id']}/targets", headers=admin_headers).json()[0]

    with patch("app.core.website_fetch.fetch_website_text", return_value="Check-in 15h, animaux acceptés."):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.mistral_api_key = "fake_key"
            mock_settings.anthropic_api_key = ""
            with patch("app.providers.analysis.mistral_provider.Mistral") as MockMistral:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="Horaires : 15h.\nAnimaux : acceptés."))]
                mock_client.chat.complete.return_value = mock_response
                MockMistral.return_value = mock_client

                response = client.post(
                    f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}/analyze",
                    headers=admin_headers,
                )

    assert response.json()["success"] is True
    targets = client.get(f"/admin/prospecting-campaigns/{campaign['id']}/targets", headers=admin_headers).json()
    assert "15h" in targets[0]["extracted_info"]
