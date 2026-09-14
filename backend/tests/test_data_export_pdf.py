"""
Tests de l'export PDF lisible du droit d'accès (section 42/43) — contrairement
au JSON brut, pensé pour être remis directement à la personne concernée.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_pdf_export_returns_valid_pdf_file(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613100001", "first_name": "Awa"}, headers=headers).json()

    response = client.get(f"/contacts/{contact['id']}/data-export-pdf", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"  # signature de fichier PDF standard


def test_pdf_export_filename_based_on_phone(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613100002"}, headers=headers).json()

    response = client.get(f"/contacts/{contact['id']}/data-export-pdf", headers=headers)
    assert "33613100002" in response.headers["content-disposition"]


def test_pdf_export_fulfills_pending_access_request(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613100003"}, headers=headers).json()
    client.post(f"/contacts/{contact['id']}/data-subject-requests", json={"request_type": "access"}, headers=headers)

    client.get(f"/contacts/{contact['id']}/data-export-pdf", headers=headers)

    requests = client.get(f"/contacts/{contact['id']}/data-subject-requests", headers=headers).json()
    assert requests[0]["status"] == "fulfilled"


def test_pdf_export_with_calls_and_consent_does_not_crash(client, db_session):
    """Test de robustesse : un contact avec beaucoup de données liées ne doit jamais faire planter la génération."""
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33613100004", "first_name": "Moussa"}, headers=headers).json()
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    db_session.add(Call(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), contact_id=uuid_module.UUID(contact["id"]),
        direction="inbound", status="completed", provider="retell", duration_seconds=180,
        transcript="Contenu de test", summary="Résumé de test", qualification="Prospect chaud",
    ))
    db_session.commit()
    client.post(
        "/consent", json={"contact_phone": "+33613100004", "source": "test", "consent_text": "Texte de consentement"},
        headers=headers,
    )

    response = client.get(f"/contacts/{contact['id']}/data-export-pdf", headers=headers)
    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"


def test_pdf_export_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613100005"}, headers=headers_a).json()

    response = client.get(f"/contacts/{contact['id']}/data-export-pdf", headers=headers_b)
    assert response.status_code == 404
