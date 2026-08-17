def test_create_and_list_contacts(client):
    org = client.post("/organizations", json={"name": "Entreprise Test"}).json()
    org_id = org["id"]

    response = client.post(
        "/contacts",
        json={"first_name": "Awa", "last_name": "Diop", "phone": "+221770000001"},
        headers={"x-organization-id": org_id},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Nouveau"

    contacts = client.get("/contacts", headers={"x-organization-id": org_id}).json()
    assert len(contacts) == 1


def test_contacts_isolated_between_organizations(client):
    org_a = client.post("/organizations", json={"name": "Entreprise A"}).json()
    org_b = client.post("/organizations", json={"name": "Entreprise B"}).json()

    client.post(
        "/contacts",
        json={"phone": "+221770000001"},
        headers={"x-organization-id": org_a["id"]},
    )

    contacts_b = client.get("/contacts", headers={"x-organization-id": org_b["id"]}).json()
    assert len(contacts_b) == 0
