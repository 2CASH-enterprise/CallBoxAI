"""
/organizations est désormais réservé au Super Admin (section 22) — la
création "libre" d'organisation se fait via /auth/register (section 6.1).
"""
from tests.conftest import auth_headers, create_super_admin, register_user


def test_super_admin_can_create_and_list_organizations(client):
    admin_token = create_super_admin(client)

    r = client.post(
        "/organizations",
        json={"name": "Entreprise A", "country": "SN"},
        headers=auth_headers(admin_token),
    )
    assert r.status_code == 200

    orgs = client.get("/organizations", headers=auth_headers(admin_token)).json()
    assert len(orgs) == 1


def test_regular_user_cannot_access_organizations_admin_route(client):
    token, _ = register_user(client)
    r = client.get("/organizations", headers=auth_headers(token))
    assert r.status_code == 403
