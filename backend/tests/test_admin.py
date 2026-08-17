"""
Tests du Dashboard Super Admin (section 22 du cahier des charges).
"""
from tests.conftest import auth_headers, create_super_admin, register_user
from tests.test_distributors import create_distributor, onboarding_payload


def test_admin_dashboard_requires_super_admin(client):
    token, _org_id = register_user(client)
    response = client.get("/admin/dashboard", headers=auth_headers(token))
    assert response.status_code == 403


def test_distributor_cannot_access_admin_dashboard(client):
    admin_token = create_super_admin(client)
    _distributor, distributor_token = create_distributor(client, admin_token)
    response = client.get("/admin/dashboard", headers=auth_headers(distributor_token))
    assert response.status_code == 403


def test_admin_dashboard_counts_direct_and_distributor_organizations(client):
    admin_token = create_super_admin(client)

    # Un client direct (inscription libre-service, sans distributeur)
    register_user(client, org_name="Client Direct")

    # Un client apporté par un distributeur
    distributor, distributor_token = create_distributor(client, admin_token)
    client.post(
        f"/distributors/{distributor['id']}/clients",
        json=onboarding_payload("Client Distributeur"),
        headers=auth_headers(distributor_token),
    )

    dashboard = client.get("/admin/dashboard", headers=auth_headers(admin_token)).json()
    assert dashboard["totals"]["organizations"] == 2
    assert dashboard["totals"]["organizations_direct"] == 1
    assert dashboard["totals"]["organizations_via_distributor"] == 1
    assert dashboard["totals"]["distributors"] == 1


def test_admin_dashboard_includes_distributor_summary_with_calls(client):
    admin_token = create_super_admin(client)
    distributor, distributor_token = create_distributor(client, admin_token)

    payload = onboarding_payload("Client X")
    client.post(
        f"/distributors/{distributor['id']}/clients", json=payload, headers=auth_headers(distributor_token)
    )
    org_login = client.post(
        "/auth/login", json={"email": payload["owner_email"], "password": payload["owner_password"]}
    ).json()
    client_token = org_login["access_token"]

    me = client.get("/auth/me", headers=auth_headers(client_token)).json()
    org_id = me["memberships"][0]["organization_id"]
    headers = {**auth_headers(client_token), "x-organization-id": org_id}

    agent = client.post("/agents", json={"name": "Agent X"}, headers=headers).json()
    client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers,
    )

    dashboard = client.get("/admin/dashboard", headers=auth_headers(admin_token)).json()
    assert dashboard["totals"]["calls_total"] == 1
    assert dashboard["totals"]["agents"] == 1
    assert len(dashboard["distributors"]) == 1
    assert dashboard["distributors"][0]["clients_count"] == 1
    assert dashboard["distributors"][0]["calls_count"] == 1

    org_row = next(o for o in dashboard["organizations"] if o["id"] == org_id)
    assert org_row["distributor_name"] == distributor["name"]
    assert org_row["calls_count"] == 1
    assert org_row["agents_count"] == 1


def test_admin_dashboard_direct_organization_has_no_distributor_name(client):
    admin_token = create_super_admin(client)
    _token, org_id = register_user(client, org_name="Client Direct Test")

    dashboard = client.get("/admin/dashboard", headers=auth_headers(admin_token)).json()
    org_row = next(o for o in dashboard["organizations"] if o["id"] == org_id)
    assert org_row["distributor_name"] is None
