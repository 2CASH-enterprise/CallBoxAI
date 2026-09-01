"""
Tests du suivi interne de marge (section 40 — Super Admin uniquement) :
coût réel en minutes face aux résultats produits, jamais exposé au client.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def get_super_admin_headers(client):
    response = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "superadmin-margin@example.com", "password": "TestPassword123", "full_name": "Admin Test"},
    )
    token = response.json()["access_token"]
    return auth_headers(token)


def test_client_cannot_access_margin_report(client):
    headers = setup_org(client)
    response = client.get("/admin/margin-report", headers=headers)
    assert response.status_code == 403


def test_margin_report_computes_real_cost_from_duration(client, db_session):
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Support"}, headers=headers).json()

    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="inbound", status="completed", provider="retell", duration_seconds=600))
    db_session.commit()

    admin_headers = get_super_admin_headers(client)
    report = client.get("/admin/margin-report", headers=admin_headers).json()
    entry = next(r for r in report if r["agent_id"] == agent["id"])

    assert entry["total_minutes"] == 10
    assert entry["real_cost_fcfa"] == 600.0  # 10 minutes * 60 FCFA (valeur par défaut)
    assert entry["is_commercial"] is False
    assert entry["results_count"] is None


def test_margin_report_computes_cost_per_result_for_commercial_agent(client, db_session):
    """Test central : un agent commercial doit exposer un coût par lead produit."""
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Prospection", "category": "prospection"}, headers=headers).json()

    # 3 appels, 2 produisent un lead qualifié (Prospect chaud), 1 non
    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="outbound", status="completed", provider="retell", duration_seconds=300, qualification="Prospect chaud"))
    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="outbound", status="completed", provider="retell", duration_seconds=300, qualification="Prospect chaud"))
    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="outbound", status="completed", provider="retell", duration_seconds=300, qualification="Pas intéressé"))
    db_session.commit()

    admin_headers = get_super_admin_headers(client)
    report = client.get("/admin/margin-report", headers=admin_headers).json()
    entry = next(r for r in report if r["agent_id"] == agent["id"])

    assert entry["is_commercial"] is True
    assert entry["results_count"] == 2
    assert entry["total_minutes"] == 15  # 900s / 60
    assert entry["real_cost_fcfa"] == 900.0
    assert entry["cost_per_result_fcfa"] == 450.0  # 900 / 2


def test_margin_report_commercial_agent_with_zero_results_has_no_cost_per_result(client, db_session):
    """Une campagne qui ne convertit rien : coût réel visible, mais pas de division par zéro."""
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Prospection Vide", "category": "prospection"}, headers=headers).json()

    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="outbound", status="completed", provider="retell", duration_seconds=600, qualification="Pas intéressé"))
    db_session.commit()

    admin_headers = get_super_admin_headers(client)
    report = client.get("/admin/margin-report", headers=admin_headers).json()
    entry = next(r for r in report if r["agent_id"] == agent["id"])

    assert entry["results_count"] == 0
    assert entry["cost_per_result_fcfa"] is None


def test_margin_report_includes_all_organizations(client):
    from tests.conftest import register_user

    token_a, org_id_a = register_user(client, org_name="Organisation Marge A")
    headers_a = {**auth_headers(token_a), "x-organization-id": org_id_a}
    token_b, org_id_b = register_user(client, org_name="Organisation Marge B")
    headers_b = {**auth_headers(token_b), "x-organization-id": org_id_b}
    client.post("/agents", json={"name": "Agent A"}, headers=headers_a)
    client.post("/agents", json={"name": "Agent B"}, headers=headers_b)

    admin_headers = get_super_admin_headers(client)
    report = client.get("/admin/margin-report", headers=admin_headers).json()
    org_names = {r["organization_name"] for r in report}
    assert {"Organisation Marge A", "Organisation Marge B"}.issubset(org_names)
