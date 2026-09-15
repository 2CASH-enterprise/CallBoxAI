"""
Tests de l'analyse automatique de site web (étape 2/N de l'outil interne de
prospection) — résilience centrale : une cible en échec ne doit jamais
bloquer le reste du lot.
"""
from unittest.mock import patch, MagicMock

from tests.conftest import auth_headers


def get_super_admin_headers(client):
    response = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "superadmin-analysis@example.com", "password": "TestPassword123", "full_name": "Admin Test"},
    )
    token = response.json()["access_token"]
    return auth_headers(token)


def _create_campaign_with_target(client, admin_headers, website_url="https://exemple-hotel.fr"):
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test analyse", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()
    csv_content = f"nom,site_internet\nHôtel Exemple,{website_url}\n" if website_url else "nom\nHôtel Sans Site\n"
    client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )
    target = client.get(f"/admin/prospecting-campaigns/{campaign['id']}/targets", headers=admin_headers).json()[0]
    return campaign, target


# ---------- Analyse d'une cible unique ----------

def test_analyze_target_without_website_fails_gracefully(client):
    admin_headers = get_super_admin_headers(client)
    campaign, target = _create_campaign_with_target(client, admin_headers, website_url=None)

    response = client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}/analyze",
        headers=admin_headers,
    )
    body = response.json()
    assert body["success"] is False
    assert "site web" in body["message"].lower()


def test_analyze_target_success_updates_status_and_info(client):
    admin_headers = get_super_admin_headers(client)
    campaign, target = _create_campaign_with_target(client, admin_headers)

    with patch("app.core.website_fetch.fetch_website_text", return_value="Check-in à 14h, animaux acceptés."):
        with patch("app.api.routes.prospecting_campaigns._get_analysis_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.extract_practical_info.return_value = "Horaires : check-in 14h.\nAnimaux : acceptés."
            mock_get_provider.return_value = mock_provider

            response = client.post(
                f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}/analyze",
                headers=admin_headers,
            )

    assert response.json()["success"] is True

    targets = client.get(f"/admin/prospecting-campaigns/{campaign['id']}/targets", headers=admin_headers).json()
    assert targets[0]["status"] == "analyzed"
    assert "check-in 14h" in targets[0]["extracted_info"]


def test_analyze_target_handles_unreachable_website(client):
    admin_headers = get_super_admin_headers(client)
    campaign, target = _create_campaign_with_target(client, admin_headers, website_url="https://site-inexistant-xyz.fr")

    with patch("app.core.website_fetch.fetch_website_text", side_effect=Exception("Connexion refusée")):
        response = client.post(
            f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}/analyze",
            headers=admin_headers,
        )

    body = response.json()
    assert body["success"] is False
    assert "injoignable" in body["message"].lower() or "erreur" in body["message"].lower()

    targets = client.get(f"/admin/prospecting-campaigns/{campaign['id']}/targets", headers=admin_headers).json()
    assert targets[0]["status"] == "imported"  # jamais marqué "analyzed" en cas d'échec


def test_analyze_target_handles_empty_website_content(client):
    admin_headers = get_super_admin_headers(client)
    campaign, target = _create_campaign_with_target(client, admin_headers)

    with patch("app.core.website_fetch.fetch_website_text", return_value="   "):
        response = client.post(
            f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}/analyze",
            headers=admin_headers,
        )
    assert response.json()["success"] is False


def test_analyze_target_handles_llm_failure(client):
    admin_headers = get_super_admin_headers(client)
    campaign, target = _create_campaign_with_target(client, admin_headers)

    with patch("app.core.website_fetch.fetch_website_text", return_value="Contenu du site."):
        with patch("app.api.routes.prospecting_campaigns._get_analysis_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.extract_practical_info.side_effect = Exception("Panne API simulée")
            mock_get_provider.return_value = mock_provider

            response = client.post(
                f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}/analyze",
                headers=admin_headers,
            )
    body = response.json()
    assert body["success"] is False
    assert "modèle de langage" in body["message"].lower()


def test_analyze_nonexistent_target_returns_404(client):
    import uuid as uuid_module

    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns", json={"name": "Test", "sector": "hôtellerie", "agent_template_key": "hotellerie"}, headers=admin_headers
    ).json()

    response = client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/targets/{uuid_module.uuid4()}/analyze",
        headers=admin_headers,
    )
    assert response.status_code == 404


# ---------- Analyse en lot (le vrai cas d'usage : 50 hôtels d'un coup) ----------

def test_bulk_analyze_processes_all_imported_targets(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns", json={"name": "Test lot", "sector": "hôtellerie", "agent_template_key": "hotellerie"}, headers=admin_headers
    ).json()
    csv_content = "nom,site_internet\nHôtel A,https://hotel-a.fr\nHôtel B,https://hotel-b.fr\n"
    client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")}, headers=admin_headers,
    )

    with patch("app.core.website_fetch.fetch_website_text", return_value="Contenu générique."):
        with patch("app.api.routes.prospecting_campaigns._get_analysis_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.extract_practical_info.return_value = "Résumé généré."
            mock_get_provider.return_value = mock_provider

            response = client.post(f"/admin/prospecting-campaigns/{campaign['id']}/analyze-all", headers=admin_headers)

    body = response.json()
    assert body["analyzed"] == 2
    assert body["failed"] == 0
    assert len(body["details"]) == 2


def test_bulk_analyze_one_failure_does_not_block_others(client):
    """Test central : une cible en échec (site injoignable) n'empêche jamais les autres d'être analysées."""
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns", json={"name": "Test résilience", "sector": "hôtellerie", "agent_template_key": "hotellerie"}, headers=admin_headers
    ).json()
    csv_content = "nom,site_internet\nHôtel Injoignable,https://injoignable.fr\nHôtel OK,https://ok.fr\n"
    client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")}, headers=admin_headers,
    )

    def fetch_side_effect(url, *args, **kwargs):
        if "injoignable" in url:
            raise Exception("Connexion refusée")
        return "Contenu du site OK."

    with patch("app.core.website_fetch.fetch_website_text", side_effect=fetch_side_effect):
        with patch("app.api.routes.prospecting_campaigns._get_analysis_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.extract_practical_info.return_value = "Résumé généré."
            mock_get_provider.return_value = mock_provider

            response = client.post(f"/admin/prospecting-campaigns/{campaign['id']}/analyze-all", headers=admin_headers)

    body = response.json()
    assert body["analyzed"] == 1
    assert body["failed"] == 1


def test_bulk_analyze_skips_already_analyzed_targets(client):
    admin_headers = get_super_admin_headers(client)
    campaign, target = _create_campaign_with_target(client, admin_headers)

    with patch("app.core.website_fetch.fetch_website_text", return_value="Contenu."):
        with patch("app.api.routes.prospecting_campaigns._get_analysis_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.extract_practical_info.return_value = "Résumé."
            mock_get_provider.return_value = mock_provider

            client.post(f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}/analyze", headers=admin_headers)
            response = client.post(f"/admin/prospecting-campaigns/{campaign['id']}/analyze-all", headers=admin_headers)

    assert response.json()["analyzed"] == 0  # déjà analysée, pas retraitée


# ---------- Fournisseur simulé (utilisé en l'absence de clé API) ----------

def test_mock_provider_never_invents_information():
    from app.providers.analysis.mock import MockWebsiteAnalysisProvider

    result = MockWebsiteAnalysisProvider().extract_practical_info("texte quelconque", "Hôtel Test")
    assert "non trouvée" in result.lower()


# ---------- Récupération et nettoyage du site (fonction réelle, sans mock) ----------

def test_fetch_website_text_strips_scripts_and_styles():
    from app.core.website_fetch import fetch_website_text

    html = "<html><body><script>alert('x')</script><style>.a{color:red}</style><p>Bonjour le monde</p></body></html>"
    with patch("httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        text = fetch_website_text("https://exemple.fr")

    assert "Bonjour le monde" in text
    assert "alert" not in text
    assert "color:red" not in text
