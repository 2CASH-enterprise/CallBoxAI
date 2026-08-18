"""
Tests de l'import en masse de contacts CRM (section 18 du cahier des charges).
"""
import io

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_import_via_upload_creates_many_contacts(client):
    headers = setup_org(client)
    csv_content = "phone,first_name,last_name\n" + "\n".join(
        f"+22177{1000000+i},Contact{i},Test" for i in range(50)
    )
    files = {"file": ("contacts.csv", io.BytesIO(csv_content.encode()), "text/csv")}

    response = client.post("/contacts/import/upload", headers=headers, files=files)
    assert response.status_code == 200
    summary = response.json()
    assert summary["imported"] == 50
    assert summary["skipped_invalid_phone"] == 0

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 50


def test_import_via_pasted_text(client):
    headers = setup_org(client)
    pasted = "phone,first_name\n+221770000001,Awa\n+221770000002,Moussa\n"

    response = client.post("/contacts/import/text", json={"content": pasted}, headers=headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary["imported"] == 2

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 2


def test_import_skips_invalid_numbers_without_failing_everything(client):
    headers = setup_org(client)
    pasted = "phone\n+221770000001\nnumero-invalide\n42\n+221770000002\n"

    response = client.post("/contacts/import/text", json={"content": pasted}, headers=headers)
    summary = response.json()
    assert summary["imported"] == 2
    assert summary["skipped_invalid_phone"] == 2


def test_import_does_not_duplicate_existing_contacts(client):
    headers = setup_org(client)
    client.post("/contacts", json={"phone": "+221770000001", "first_name": "Déjà là"}, headers=headers)

    response = client.post(
        "/contacts/import/text", json={"content": "phone\n+221770000001\n+221770000002\n"}, headers=headers
    )
    assert response.json()["imported"] == 2  # les deux comptent comme "traités"

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 2  # mais pas de doublon pour le premier


def test_import_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)

    client.post("/contacts/import/text", json={"content": "phone\n+221770000001\n"}, headers=headers_a)

    contacts_b = client.get("/contacts", headers=headers_b).json()
    assert len(contacts_b) == 0
