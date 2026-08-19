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


def test_import_recognizes_french_column_names(client):
    """
    Bug réel corrigé : un export avec les colonnes "nom"/"telephone" (au lieu
    de "first_name"/"phone") doit être reconnu automatiquement.
    """
    headers = setup_org(client)
    csv_content = "nom,adresse,ville,telephone,note_google\nHotel Test,Adresse,Paris,+33 1 78 90 78 10,4.4\n"

    response = client.post("/contacts/import/text", json={"content": csv_content}, headers=headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary["imported"] == 1
    assert summary["skipped_invalid_phone"] == 0

    contact = client.get("/contacts", headers=headers).json()[0]
    assert contact["first_name"] == "Hotel Test"
    assert contact["phone"] == "+33178907810"  # espaces retirés


def test_import_cleans_formatted_phone_numbers(client):
    """Numéros avec espaces, tirets, points, parenthèses — tous doivent être acceptés et nettoyés."""
    headers = setup_org(client)
    csv_content = (
        "phone\n"
        "+33 1 78 90 78 10\n"
        "+33-1-78-90-78-11\n"
        "+33.1.78.90.78.12\n"
        "+33 (1) 78 90 78 13\n"
    )

    response = client.post("/contacts/import/text", json={"content": csv_content}, headers=headers)
    summary = response.json()
    assert summary["imported"] == 4
    assert summary["skipped_invalid_phone"] == 0

    contacts = client.get("/contacts", headers=headers).json()
    phones = {c["phone"] for c in contacts}
    assert phones == {"+33178907810", "+33178907811", "+33178907812", "+33178907813"}


def test_import_still_ignores_genuinely_empty_or_invalid_phones(client):
    headers = setup_org(client)
    csv_content = "nom,telephone\nHotel Sans Numéro,\nHotel Numéro Invalide,abc\n"

    response = client.post("/contacts/import/text", json={"content": csv_content}, headers=headers)
    summary = response.json()
    assert summary["imported"] == 0
    assert summary["skipped_invalid_phone"] == 2
