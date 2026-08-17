"""
Test critique : vérifie le principe fondamental de la section 3 du cahier des
charges — les données d'une entreprise ne doivent JAMAIS être visibles par une
autre, même par un utilisateur authentifié appartenant à une autre entreprise.
"""
from tests.conftest import auth_headers, register_user


def test_agent_isolation_between_organizations(client):
    token_a, org_a_id = register_user(client, org_name="Entreprise A")
    token_b, org_b_id = register_user(client, org_name="Entreprise B")

    client.post(
        "/agents",
        json={"name": "Agent commercial A"},
        headers={**auth_headers(token_a), "x-organization-id": org_a_id},
    )
    client.post(
        "/agents",
        json={"name": "Agent commercial B"},
        headers={**auth_headers(token_b), "x-organization-id": org_b_id},
    )

    agents_a = client.get("/agents", headers={**auth_headers(token_a), "x-organization-id": org_a_id}).json()
    assert len(agents_a) == 1
    assert agents_a[0]["name"] == "Agent commercial A"

    agents_b = client.get("/agents", headers={**auth_headers(token_b), "x-organization-id": org_b_id}).json()
    assert len(agents_b) == 1
    assert agents_b[0]["name"] == "Agent commercial B"


def test_user_cannot_access_another_organizations_data_even_with_valid_token(client):
    """
    Un utilisateur authentifié et valide, mais qui n'est PAS membre de
    l'organisation ciblée, doit être rejeté (403) — même s'il essaie de
    passer le bon organization_id dans le header.
    """
    token_a, org_a_id = register_user(client, org_name="Entreprise A")
    _token_b, org_b_id = register_user(client, org_name="Entreprise B")

    # token_a essaie d'accéder aux données de l'organisation B
    response = client.get("/agents", headers={**auth_headers(token_a), "x-organization-id": org_b_id})
    assert response.status_code == 403
