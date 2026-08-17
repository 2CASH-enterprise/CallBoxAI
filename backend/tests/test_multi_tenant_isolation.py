"""
Test critique : vérifie le principe fondamental de la section 3 du cahier des
charges — les données d'une entreprise ne doivent JAMAIS être visibles par une autre.
"""


def create_org(client, name):
    r = client.post("/organizations", json={"name": name})
    return r.json()["id"]


def test_agent_isolation_between_organizations(client):
    org_a_id = create_org(client, "Entreprise A")
    org_b_id = create_org(client, "Entreprise B")

    # Entreprise A crée un agent
    client.post(
        "/agents",
        json={"name": "Agent commercial A"},
        headers={"x-organization-id": org_a_id},
    )

    # Entreprise B crée un agent
    client.post(
        "/agents",
        json={"name": "Agent commercial B"},
        headers={"x-organization-id": org_b_id},
    )

    # Entreprise A ne doit voir QUE ses propres agents
    response_a = client.get("/agents", headers={"x-organization-id": org_a_id})
    agents_a = response_a.json()
    assert len(agents_a) == 1
    assert agents_a[0]["name"] == "Agent commercial A"

    # Entreprise B ne doit voir QUE ses propres agents
    response_b = client.get("/agents", headers={"x-organization-id": org_b_id})
    agents_b = response_b.json()
    assert len(agents_b) == 1
    assert agents_b[0]["name"] == "Agent commercial B"
