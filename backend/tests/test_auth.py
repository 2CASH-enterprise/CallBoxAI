"""
Tests du module d'authentification (section 24 du cahier des charges).
"""
from tests.conftest import auth_headers, register_user, create_super_admin


def test_register_creates_user_and_organization_as_owner(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "awa@example.com",
            "password": "password123",
            "full_name": "Awa Diop",
            "organization_name": "Awa Corp",
        },
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/auth/me", headers=auth_headers(token)).json()
    assert me["email"] == "awa@example.com"
    assert me["is_super_admin"] is False
    assert len(me["memberships"]) == 1
    assert me["memberships"][0]["role"] == "owner"


def test_register_rejects_duplicate_email(client):
    client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "password123", "full_name": "A", "organization_name": "Org A"},
    )
    r = client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "password123", "full_name": "B", "organization_name": "Org B"},
    )
    assert r.status_code == 400


def test_register_rejects_short_password(client):
    r = client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "abc", "full_name": "A", "organization_name": "Org"},
    )
    assert r.status_code == 422


def test_login_succeeds_with_correct_credentials(client):
    client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "password123", "full_name": "A", "organization_name": "Org"},
    )
    r = client.post("/auth/login", json={"email": "login@example.com", "password": "password123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_rejects_wrong_password(client):
    client.post(
        "/auth/register",
        json={"email": "wrong@example.com", "password": "password123", "full_name": "A", "organization_name": "Org"},
    )
    r = client.post("/auth/login", json={"email": "wrong@example.com", "password": "mauvais-mdp"})
    assert r.status_code == 401


def test_protected_route_rejects_missing_token(client):
    r = client.get("/agents", headers={"x-organization-id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 401


def test_protected_route_rejects_invalid_token(client):
    r = client.get(
        "/agents",
        headers={"x-organization-id": "00000000-0000-0000-0000-000000000000", "Authorization": "Bearer token-invalide"},
    )
    assert r.status_code == 401


def test_bootstrap_super_admin_only_works_once(client):
    r1 = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "admin1@example.com", "password": "password123", "full_name": "Admin 1"},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "admin2@example.com", "password": "password123", "full_name": "Admin 2"},
    )
    assert r2.status_code == 403
