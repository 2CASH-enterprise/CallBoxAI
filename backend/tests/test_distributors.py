"""
Tests du module Distributeur (section 39 du cahier des charges), avec les
vraies règles d'accès : création réservée au Super Admin, portefeuille
consultable uniquement par le Super Admin ou le distributeur concerné.
"""
import uuid

from tests.conftest import auth_headers, create_super_admin, register_user


def create_distributor(client, admin_token, name="Jean K", password="password123"):
    email = f"distributeur-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/distributors",
        json={"name": name, "email": email, "password": password, "country": "SN", "commission_rate": 10.0},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200, r.text
    distributor = r.json()

    # Connexion avec le compte créé automatiquement pour ce distributeur
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    distributor_token = login.json()["access_token"]

    return distributor, distributor_token


def test_only_super_admin_can_create_distributor(client):
    token, _ = register_user(client)  # utilisateur normal, pas Super Admin
    r = client.post(
        "/distributors",
        json={"name": "X", "email": "x@example.com", "password": "password123"},
        headers=auth_headers(token),
    )
    assert r.status_code == 403


def test_distributor_creation_also_creates_its_login(client):
    admin_token = create_super_admin(client)
    distributor, distributor_token = create_distributor(client, admin_token)

    me = client.get("/auth/me", headers=auth_headers(distributor_token)).json()
    assert me["distributor_id"] == distributor["id"]


def test_onboard_client_attaches_distributor_id(client):
    admin_token = create_super_admin(client)
    distributor, distributor_token = create_distributor(client, admin_token)

    r = client.post(
        f"/distributors/{distributor['id']}/clients",
        json={"name": "Client Onboardé", "country": "SN"},
        headers=auth_headers(distributor_token),
    )
    assert r.status_code == 200

    clients = client.get(
        f"/distributors/{distributor['id']}/clients", headers=auth_headers(distributor_token)
    ).json()
    assert len(clients) == 1


def test_distributor_isolation_between_portfolios(client):
    """
    Test critique : un distributeur ne doit JAMAIS voir les clients d'un
    autre distributeur — même en étant authentifié avec un token valide.
    """
    admin_token = create_super_admin(client)
    dist_a, token_a = create_distributor(client, admin_token, name="Distributeur A")
    dist_b, token_b = create_distributor(client, admin_token, name="Distributeur B")

    client.post(
        f"/distributors/{dist_a['id']}/clients", json={"name": "Client de A"}, headers=auth_headers(token_a)
    )
    client.post(
        f"/distributors/{dist_b['id']}/clients", json={"name": "Client de B"}, headers=auth_headers(token_b)
    )

    # Distributeur A ne peut même pas CONSULTER le portefeuille de B
    forbidden = client.get(f"/distributors/{dist_b['id']}/clients", headers=auth_headers(token_a))
    assert forbidden.status_code == 403

    clients_a = client.get(f"/distributors/{dist_a['id']}/clients", headers=auth_headers(token_a)).json()
    assert len(clients_a) == 1
    assert clients_a[0]["name"] == "Client de A"


def test_super_admin_can_access_any_distributor_portfolio(client):
    admin_token = create_super_admin(client)
    distributor, distributor_token = create_distributor(client, admin_token)
    client.post(
        f"/distributors/{distributor['id']}/clients",
        json={"name": "Client X"},
        headers=auth_headers(distributor_token),
    )

    response = client.get(f"/distributors/{distributor['id']}/clients", headers=auth_headers(admin_token))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_dashboard_aggregates_calls_across_portfolio(client):
    admin_token = create_super_admin(client)
    distributor, distributor_token = create_distributor(client, admin_token)

    org = client.post(
        f"/distributors/{distributor['id']}/clients",
        json={"name": "Client X"},
        headers=auth_headers(distributor_token),
    ).json()

    # Le distributeur n'a pas de compte dans l'organisation cliente elle-même ;
    # c'est le Super Admin qui simule ici l'activité du client pour le test.
    owner_token, _ = register_user(client, org_name="Peu importe")
    # On force l'organization_id du header à celui du client onboardé, en tant
    # que Super Admin (seul autorisé à agir pour n'importe quelle organisation).
    headers = {**auth_headers(admin_token), "x-organization-id": org["id"]}

    agent = client.post("/agents", json={"name": "Agent X"}, headers=headers).json()
    for _ in range(2):
        client.post(
            "/calls",
            json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
            headers=headers,
        )

    dashboard = client.get(
        f"/distributors/{distributor['id']}/dashboard", headers=auth_headers(distributor_token)
    ).json()
    assert dashboard["total_clients"] == 1
    assert dashboard["total_calls"] == 2
    assert dashboard["estimated_commission_current_period"] == 100.0  # 2 * 500 * 10%


def test_calculate_commissions_persists_records(client):
    admin_token = create_super_admin(client)
    distributor, distributor_token = create_distributor(client, admin_token)

    org = client.post(
        f"/distributors/{distributor['id']}/clients",
        json={"name": "Client Y"},
        headers=auth_headers(distributor_token),
    ).json()

    headers = {**auth_headers(admin_token), "x-organization-id": org["id"]}
    agent = client.post("/agents", json={"name": "Agent Y"}, headers=headers).json()
    client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers,
    )

    response = client.post(
        f"/distributors/{distributor['id']}/commissions/calculate", headers=auth_headers(distributor_token)
    )
    assert response.status_code == 200
    commissions = response.json()
    assert len(commissions) == 1
    assert commissions[0]["commission_amount"] == 50.0  # 1 appel * 500 * 10%

    listed = client.get(
        f"/distributors/{distributor['id']}/commissions", headers=auth_headers(distributor_token)
    ).json()
    assert len(listed) == 1

    # Idempotent
    client.post(f"/distributors/{distributor['id']}/commissions/calculate", headers=auth_headers(distributor_token))
    listed_again = client.get(
        f"/distributors/{distributor['id']}/commissions", headers=auth_headers(distributor_token)
    ).json()
    assert len(listed_again) == 1


def test_only_super_admin_can_update_commission_rate(client):
    admin_token = create_super_admin(client)
    distributor, distributor_token = create_distributor(client, admin_token)

    # Le distributeur lui-même ne peut PAS changer son propre taux
    forbidden = client.patch(
        f"/distributors/{distributor['id']}/commission-rate",
        json={"commission_rate": 50.0},
        headers=auth_headers(distributor_token),
    )
    assert forbidden.status_code == 403

    allowed = client.patch(
        f"/distributors/{distributor['id']}/commission-rate",
        json={"commission_rate": 15.0},
        headers=auth_headers(admin_token),
    )
    assert allowed.status_code == 200
    assert allowed.json()["commission_rate"] == 15.0
