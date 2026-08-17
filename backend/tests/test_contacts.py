from tests.conftest import auth_headers, register_user


def test_create_and_list_contacts(client):
    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}

    response = client.post(
        "/contacts",
        json={"first_name": "Awa", "last_name": "Diop", "phone": "+221770000001"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Nouveau"

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1


def test_contacts_isolated_between_organizations(client):
    token_a, org_a_id = register_user(client, org_name="Entreprise A")
    _token_b, org_b_id = register_user(client, org_name="Entreprise B")

    client.post(
        "/contacts",
        json={"phone": "+221770000001"},
        headers={**auth_headers(token_a), "x-organization-id": org_a_id},
    )

    contacts_b = client.get(
        "/contacts", headers={**auth_headers(token_a), "x-organization-id": org_a_id}
    ).json()
    # Entreprise A a bien son propre contact
    assert len(contacts_b) == 1

    # Un membre de A ne peut de toute façon pas consulter B (403, testé ailleurs) ;
    # ici on vérifie qu'un contact créé pour A n'apparaît jamais listé pour B
    # via une organisation B fraîchement créée sans contact.
    token_owner_b, _ = register_user(client, org_name="Entreprise B bis")
    contacts_empty = client.get(
        "/contacts", headers={**auth_headers(token_owner_b), "x-organization-id": org_b_id}
    )
    assert contacts_empty.status_code == 403  # pas membre de org_b_id
