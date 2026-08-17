def test_create_organization(client):
    response = client.post("/organizations", json={"name": "Entreprise A", "country": "SN"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Entreprise A"
    assert "id" in data


def test_list_organizations(client):
    client.post("/organizations", json={"name": "Entreprise A"})
    client.post("/organizations", json={"name": "Entreprise B"})
    response = client.get("/organizations")
    assert response.status_code == 200
    assert len(response.json()) == 2
