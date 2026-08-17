"""
Tests du module Distributeur (section 39 du cahier des charges).
"""


import uuid


def create_distributor(client, name="Jean K", email=None):
    email = email or f"distributeur-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/distributors",
        json={"name": name, "email": email, "country": "SN", "commission_rate": 10.0},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_create_distributor(client):
    d = create_distributor(client)
    assert d["commission_rate"] == 10.0
    assert d["status"] == "active"


def test_onboard_client_attaches_distributor_id(client):
    d = create_distributor(client)
    r = client.post(f"/distributors/{d['id']}/clients", json={"name": "Client Onboardé", "country": "SN"})
    assert r.status_code == 200
    org = r.json()

    clients = client.get(f"/distributors/{d['id']}/clients").json()
    assert len(clients) == 1
    assert clients[0]["id"] == org["id"]


def test_distributor_isolation_between_portfolios(client):
    """
    Test critique : un distributeur ne doit JAMAIS voir les clients d'un autre
    distributeur, ni les clients directs (sans distributeur).
    """
    dist_a = create_distributor(client, name="Distributeur A")
    dist_b = create_distributor(client, name="Distributeur B")

    client.post(f"/distributors/{dist_a['id']}/clients", json={"name": "Client de A"})
    client.post(f"/distributors/{dist_b['id']}/clients", json={"name": "Client de B"})
    # Client direct, sans distributeur (créé via /organizations, comme un client autonome)
    client.post("/organizations", json={"name": "Client direct"})

    clients_a = client.get(f"/distributors/{dist_a['id']}/clients").json()
    clients_b = client.get(f"/distributors/{dist_b['id']}/clients").json()

    assert len(clients_a) == 1
    assert clients_a[0]["name"] == "Client de A"

    assert len(clients_b) == 1
    assert clients_b[0]["name"] == "Client de B"


def test_dashboard_aggregates_calls_across_portfolio(client):
    d = create_distributor(client)

    org = client.post(f"/distributors/{d['id']}/clients", json={"name": "Client X"}).json()
    agent = client.post(
        "/agents",
        json={"name": "Agent X"},
        headers={"x-organization-id": org["id"]},
    ).json()

    # 2 appels simulés pour ce client
    for _ in range(2):
        client.post(
            "/calls",
            json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
            headers={"x-organization-id": org["id"]},
        )

    dashboard = client.get(f"/distributors/{d['id']}/dashboard").json()
    assert dashboard["total_clients"] == 1
    assert dashboard["total_calls"] == 2
    # 2 appels * 500 FCFA * 10% = 100 FCFA
    assert dashboard["estimated_commission_current_period"] == 100.0


def test_calculate_commissions_persists_records(client):
    d = create_distributor(client)
    org = client.post(f"/distributors/{d['id']}/clients", json={"name": "Client Y"}).json()
    agent = client.post(
        "/agents",
        json={"name": "Agent Y"},
        headers={"x-organization-id": org["id"]},
    ).json()
    client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers={"x-organization-id": org["id"]},
    )

    response = client.post(f"/distributors/{d['id']}/commissions/calculate")
    assert response.status_code == 200
    commissions = response.json()
    assert len(commissions) == 1
    assert commissions[0]["commission_amount"] == 50.0  # 1 appel * 500 * 10%

    # Persisté : on le retrouve via GET
    listed = client.get(f"/distributors/{d['id']}/commissions").json()
    assert len(listed) == 1

    # Idempotent : recalculer ne crée pas de doublon
    client.post(f"/distributors/{d['id']}/commissions/calculate")
    listed_again = client.get(f"/distributors/{d['id']}/commissions").json()
    assert len(listed_again) == 1


def test_update_commission_rate(client):
    d = create_distributor(client)
    response = client.patch(f"/distributors/{d['id']}/commission-rate", json={"commission_rate": 15.0})
    assert response.status_code == 200
    assert response.json()["commission_rate"] == 15.0
