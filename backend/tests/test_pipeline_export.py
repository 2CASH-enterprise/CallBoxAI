"""
Tests du pipeline de qualification et de l'export CSV des leads
(sections 18/19 du cahier des charges).
"""
import csv
import io

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_pipeline_counts_contacts_by_stage(client):
    headers = setup_org(client)
    client.post("/contacts", json={"phone": "+221770000001"}, headers=headers)  # Nouveau
    client.post("/contacts", json={"phone": "+221770000002", "status": "Intéressé"}, headers=headers)
    client.post("/contacts", json={"phone": "+221770000003", "status": "RDV"}, headers=headers)
    client.post("/contacts", json={"phone": "+221770000004", "status": "Pas intéressé"}, headers=headers)

    pipeline = client.get("/contacts/pipeline", headers=headers).json()
    assert pipeline["total_contacts"] == 4

    funnel_by_status = {s["status"]: s["count"] for s in pipeline["funnel"]}
    assert funnel_by_status["Nouveau"] == 1
    assert funnel_by_status["Intéressé"] == 1
    assert funnel_by_status["RDV"] == 1

    side_by_status = {s["status"]: s["count"] for s in pipeline["side_buckets"]}
    assert side_by_status["Pas intéressé"] == 1


def test_pipeline_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    client.post("/contacts", json={"phone": "+221770000001"}, headers=headers_a)

    pipeline_b = client.get("/contacts/pipeline", headers=headers_b).json()
    assert pipeline_b["total_contacts"] == 0


def test_export_contacts_without_filter_includes_all(client):
    headers = setup_org(client)
    client.post("/contacts", json={"phone": "+221770000001", "first_name": "Awa", "status": "Intéressé"}, headers=headers)
    client.post("/contacts", json={"phone": "+221770000002", "first_name": "Moussa", "status": "Nouveau"}, headers=headers)

    response = client.get("/contacts/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["phone", "first_name", "last_name", "email", "status", "last_call_qualification", "last_call_score", "last_call_intent", "last_call_date"]
    assert len(rows) == 3  # en-tête + 2 contacts


def test_export_contacts_filtered_by_status(client):
    headers = setup_org(client)
    client.post("/contacts", json={"phone": "+221770000001", "status": "Intéressé"}, headers=headers)
    client.post("/contacts", json={"phone": "+221770000002", "status": "Nouveau"}, headers=headers)

    response = client.get("/contacts/export?status=Intéressé", headers=headers)
    rows = list(csv.reader(io.StringIO(response.text)))
    assert len(rows) == 2  # en-tête + 1 seul contact "Intéressé"
    assert rows[1][0] == "+221770000001"


def test_export_rejects_invalid_status(client):
    headers = setup_org(client)
    response = client.get("/contacts/export?status=NimportQuoi", headers=headers)
    assert response.status_code == 400


def test_export_enriched_with_last_call_qualification(client):
    """L'export doit inclure la qualification du dernier appel, pas seulement les champs bruts du contact."""
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    contact = client.post("/contacts", json={"phone": "+221770000001"}, headers=headers).json()

    client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000001", "from_number": "+221780000000", "contact_id": contact["id"]},
        headers=headers,
    )

    response = client.get("/contacts/export", headers=headers)
    rows = list(csv.reader(io.StringIO(response.text)))
    data_row = rows[1]
    # last_call_qualification (index 4) doit être rempli, pas vide
    assert data_row[4] != ""


def test_export_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    client.post("/contacts", json={"phone": "+221770000001"}, headers=headers_a)

    response = client.get("/contacts/export", headers=headers_b)
    rows = list(csv.reader(io.StringIO(response.text)))
    assert len(rows) == 1  # en-tête seulement
