"""
Tests du socle de l'outil interne de prospection Super Admin (étape 1/N) —
générique par secteur, jamais visible des clients.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def get_super_admin_headers(client):
    response = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "superadmin-prospecting@example.com", "password": "TestPassword123", "full_name": "Admin Test"},
    )
    token = response.json()["access_token"]
    return auth_headers(token)


# ---------- Accès réservé au Super Admin ----------

def test_create_campaign_requires_super_admin(client):
    headers = setup_org(client)
    response = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=headers,
    )
    assert response.status_code == 403


# ---------- Création et généricité par secteur ----------

def test_create_campaign(client):
    admin_headers = get_super_admin_headers(client)
    response = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Hôtels lot 1", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    )
    body = response.json()
    assert body["name"] == "Hôtels lot 1"
    assert body["sector"] == "hôtellerie"
    assert body["targets_count"] == 0


def test_create_campaign_for_different_sector(client):
    """Confirme la généricité : un autre secteur, un autre modèle d'agent, sans rien coder de spécifique."""
    admin_headers = get_super_admin_headers(client)
    response = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Centres de formation lot 1", "sector": "formation", "agent_template_key": "prospection_b2c"},
        headers=admin_headers,
    )
    assert response.json()["sector"] == "formation"
    assert response.json()["agent_template_key"] == "prospection_b2c"


def test_list_campaigns_shows_targets_count(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test count", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()

    csv_content = "nom,adresse,site_internet\nHôtel Test,1 rue de la Paix,https://hoteltest.fr\n"
    client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )

    campaigns = client.get("/admin/prospecting-campaigns", headers=admin_headers).json()
    found = next(c for c in campaigns if c["id"] == campaign["id"])
    assert found["targets_count"] == 1


# ---------- Import CSV, avec les alias de colonnes Atout France ----------

def test_import_recognizes_atout_france_style_columns(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Hôtels lot 1", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()

    csv_content = (
        "NOM COMMERCIAL,ADRESSE,SITE INTERNET\n"
        "1924 HÔTEL,2 Rue Gabriel Péri,https://www.1924hotel.com/\n"
    )
    response = client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )
    assert response.json()["imported"] == 1

    targets = client.get(f"/admin/prospecting-campaigns/{campaign['id']}/targets", headers=admin_headers).json()
    assert targets[0]["company_name"] == "1924 HÔTEL"
    assert targets[0]["website_url"] == "https://www.1924hotel.com/"
    assert targets[0]["status"] == "imported"


def test_import_rejects_file_without_company_column(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()

    csv_content = "adresse\n1 rue de la Paix\n"
    response = client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_import_skips_rows_without_company_name(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()

    csv_content = "nom,adresse\nHôtel A,1 rue X\n,2 rue Y\nHôtel B,3 rue Z\n"
    response = client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )
    body = response.json()
    assert body["imported"] == 2
    assert body["skipped"] == 1


# ---------- Plafond de 50 cibles par campagne (décidé avec l'utilisateur) ----------

def test_import_enforces_50_targets_cap(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test plafond", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()

    rows = "\n".join(f"Hôtel {i}" for i in range(60))
    csv_content = f"nom\n{rows}\n"
    response = client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )
    body = response.json()
    assert body["imported"] == 50
    assert body["skipped"] == 10
    assert body["total_in_campaign"] == 50


def test_import_rejects_when_campaign_already_full(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test complet", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()

    rows = "\n".join(f"Hôtel {i}" for i in range(50))
    csv_content = f"nom\n{rows}\n"
    client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )

    response = client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", "nom\nHôtel En Trop\n", "text/csv")},
        headers=admin_headers,
    )
    assert response.status_code == 400


# ---------- Vérification humaine (édition manuelle d'une cible) ----------

def test_update_target_for_human_verification(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()
    client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", "nom\nHôtel Brut\n", "text/csv")},
        headers=admin_headers,
    )
    target = client.get(f"/admin/prospecting-campaigns/{campaign['id']}/targets", headers=admin_headers).json()[0]

    response = client.patch(
        f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}",
        json={"extracted_info": "Corrigé à la main après vérification.", "status": "analyzed"},
        headers=admin_headers,
    )
    body = response.json()
    assert body["extracted_info"] == "Corrigé à la main après vérification."
    assert body["status"] == "analyzed"


def test_update_target_rejects_invalid_status(client):
    admin_headers = get_super_admin_headers(client)
    campaign = client.post(
        "/admin/prospecting-campaigns",
        json={"name": "Test", "sector": "hôtellerie", "agent_template_key": "hotellerie"},
        headers=admin_headers,
    ).json()
    client.post(
        f"/admin/prospecting-campaigns/{campaign['id']}/import",
        files={"file": ("cibles.csv", "nom\nHôtel Test\n", "text/csv")},
        headers=admin_headers,
    )
    target = client.get(f"/admin/prospecting-campaigns/{campaign['id']}/targets", headers=admin_headers).json()[0]

    response = client.patch(
        f"/admin/prospecting-campaigns/{campaign['id']}/targets/{target['id']}",
        json={"status": "statut_n_importe_quoi"},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_update_target_from_wrong_campaign_returns_404(client):
    admin_headers = get_super_admin_headers(client)
    campaign_a = client.post(
        "/admin/prospecting-campaigns", json={"name": "A", "sector": "hôtellerie", "agent_template_key": "hotellerie"}, headers=admin_headers
    ).json()
    campaign_b = client.post(
        "/admin/prospecting-campaigns", json={"name": "B", "sector": "hôtellerie", "agent_template_key": "hotellerie"}, headers=admin_headers
    ).json()
    client.post(
        f"/admin/prospecting-campaigns/{campaign_a['id']}/import",
        files={"file": ("cibles.csv", "nom\nHôtel A\n", "text/csv")}, headers=admin_headers,
    )
    target = client.get(f"/admin/prospecting-campaigns/{campaign_a['id']}/targets", headers=admin_headers).json()[0]

    response = client.patch(
        f"/admin/prospecting-campaigns/{campaign_b['id']}/targets/{target['id']}",
        json={"status": "analyzed"}, headers=admin_headers,
    )
    assert response.status_code == 404
