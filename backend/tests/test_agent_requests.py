"""
Tests du système de demande de création d'agent (section 41 du cahier des
charges) — le client décrit son besoin, le Super Admin crée l'agent.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def get_super_admin_headers(client):
    response = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "superadmin@example.com", "password": "TestPassword123", "full_name": "Admin Test"},
    )
    token = response.json()["access_token"]
    return auth_headers(token)


def test_client_can_create_agent_request(client):
    headers = setup_org(client)
    response = client.post(
        "/agent-requests",
        json={"use_case": "hotellerie", "objective": "Un agent pour gérer les réservations de mon hôtel de 20 chambres"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["use_case"] == "hotellerie"


def test_client_can_list_own_requests_only(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    client.post("/agent-requests", json={"use_case": "telecom", "objective": "Test A"}, headers=headers_a)
    client.post("/agent-requests", json={"use_case": "telecom", "objective": "Test B"}, headers=headers_b)

    requests_a = client.get("/agent-requests", headers=headers_a).json()
    assert len(requests_a) == 1
    assert requests_a[0]["objective"] == "Test A"


def test_client_cannot_access_admin_agent_requests_endpoint(client):
    headers = setup_org(client)
    response = client.get("/admin/agent-requests", headers=headers)
    assert response.status_code == 403


def test_super_admin_sees_all_requests_across_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    client.post("/agent-requests", json={"use_case": "hotellerie", "objective": "Demande A"}, headers=headers_a)
    client.post("/agent-requests", json={"use_case": "telecom", "objective": "Demande B"}, headers=headers_b)

    admin_headers = get_super_admin_headers(client)
    all_requests = client.get("/admin/agent-requests", headers=admin_headers).json()
    assert len(all_requests) == 2
    assert {r["objective"] for r in all_requests} == {"Demande A", "Demande B"}
    # Le nom de l'organisation doit être présent, pas juste son ID (utile pour l'admin)
    assert all(r["organization_name"] for r in all_requests)


def test_super_admin_can_filter_requests_by_status(client):
    headers = setup_org(client)
    admin_headers = get_super_admin_headers(client)
    req = client.post("/agent-requests", json={"use_case": "hotellerie", "objective": "Test"}, headers=headers).json()
    client.patch(f"/admin/agent-requests/{req['id']}", json={"status": "in_progress"}, headers=admin_headers)

    pending = client.get("/admin/agent-requests?status=pending", headers=admin_headers).json()
    in_progress = client.get("/admin/agent-requests?status=in_progress", headers=admin_headers).json()
    assert len(pending) == 0
    assert len(in_progress) == 1


def test_super_admin_can_reject_request_with_notes(client):
    headers = setup_org(client)
    admin_headers = get_super_admin_headers(client)
    req = client.post("/agent-requests", json={"use_case": "autre", "objective": "Demande floue"}, headers=headers).json()

    response = client.patch(
        f"/admin/agent-requests/{req['id']}",
        json={"status": "rejected", "admin_notes": "Merci de préciser le secteur d'activité"},
        headers=admin_headers,
    )
    assert response.json()["status"] == "rejected"
    assert response.json()["admin_notes"] == "Merci de préciser le secteur d'activité"


def test_super_admin_fulfilling_request_creates_real_agent_for_correct_organization(client):
    """Test central : l'agent créé doit appartenir à L'ORGANISATION DU CLIENT, pas au Super Admin (qui n'en a aucune)."""
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    admin_headers = get_super_admin_headers(client)

    req = client.post(
        "/agent-requests",
        json={"use_case": "hotellerie", "objective": "Réceptionniste pour mon hôtel"},
        headers=headers,
    ).json()

    response = client.post(
        f"/admin/agent-requests/{req['id']}/fulfill",
        json={"name": "Agent Réceptionniste", "category": "hotellerie", "objective": "Réservations"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["created_agent_id"] is not None

    # L'agent doit apparaître dans la liste du CLIENT, pas ailleurs
    agents = client.get("/agents", headers=headers).json()
    assert len(agents) == 1
    assert agents[0]["id"] == body["created_agent_id"]
    assert agents[0]["category"] == "hotellerie"


def test_cannot_fulfill_already_completed_request(client):
    headers = setup_org(client)
    admin_headers = get_super_admin_headers(client)
    req = client.post("/agent-requests", json={"use_case": "hotellerie", "objective": "Test"}, headers=headers).json()

    client.post(f"/admin/agent-requests/{req['id']}/fulfill", json={"name": "Agent 1"}, headers=admin_headers)
    second_attempt = client.post(f"/admin/agent-requests/{req['id']}/fulfill", json={"name": "Agent 2"}, headers=admin_headers)

    assert second_attempt.status_code == 400


def test_client_cannot_fulfill_requests(client):
    headers = setup_org(client)
    req = client.post("/agent-requests", json={"use_case": "hotellerie", "objective": "Test"}, headers=headers).json()

    response = client.post(f"/admin/agent-requests/{req['id']}/fulfill", json={"name": "Agent"}, headers=headers)
    assert response.status_code == 403


def test_fulfilled_agent_has_source_template_traced(client):
    """Le modèle d'origine doit être mémorisé automatiquement, sans que l'admin ait à le préciser."""
    headers = setup_org(client)
    admin_headers = get_super_admin_headers(client)
    req = client.post("/agent-requests", json={"use_case": "telecom", "objective": "Test"}, headers=headers).json()

    client.post(f"/admin/agent-requests/{req['id']}/fulfill", json={"name": "Agent Télécom"}, headers=admin_headers)

    agents = client.get("/agents", headers=headers).json()
    assert agents[0]["source_template"] == "telecom"


def test_super_admin_can_list_all_agents_across_organizations(client):
    from tests.conftest import register_user
    token_a, org_id_a = register_user(client, org_name="Organisation A")
    headers_a = {**auth_headers(token_a), "x-organization-id": org_id_a}
    token_b, org_id_b = register_user(client, org_name="Organisation B")
    headers_b = {**auth_headers(token_b), "x-organization-id": org_id_b}
    admin_headers = get_super_admin_headers(client)
    req_a = client.post("/agent-requests", json={"use_case": "hotellerie", "objective": "Test A"}, headers=headers_a).json()
    req_b = client.post("/agent-requests", json={"use_case": "telecom", "objective": "Test B"}, headers=headers_b).json()
    client.post(f"/admin/agent-requests/{req_a['id']}/fulfill", json={"name": "Agent A"}, headers=admin_headers)
    client.post(f"/admin/agent-requests/{req_b['id']}/fulfill", json={"name": "Agent B"}, headers=admin_headers)

    all_agents = client.get("/admin/agents", headers=admin_headers).json()
    assert len(all_agents) == 2
    organization_names = {a["organization_name"] for a in all_agents}
    assert organization_names == {"Organisation A", "Organisation B"}


def test_client_cannot_access_admin_agents_endpoint(client):
    headers = setup_org(client)
    response = client.get("/admin/agents", headers=headers)
    assert response.status_code == 403


def test_super_admin_can_update_agent_prompt_for_any_organization(client):
    """Test central : le Super Admin modifie un agent d'une organisation dont il n'est pas membre."""
    headers = setup_org(client)
    admin_headers = get_super_admin_headers(client)
    req = client.post("/agent-requests", json={"use_case": "hotellerie", "objective": "Test"}, headers=headers).json()
    result = client.post(f"/admin/agent-requests/{req['id']}/fulfill", json={"name": "Agent Hôtel", "system_prompt": "Ancien prompt"}, headers=admin_headers).json()
    agent_id = result["created_agent_id"]

    response = client.patch(f"/admin/agents/{agent_id}", json={"system_prompt": "Nouveau prompt amélioré"}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["system_prompt"] == "Nouveau prompt amélioré"

    # Confirmé aussi côté client
    agents = client.get("/agents", headers=headers).json()
    assert agents[0]["system_prompt"] == "Nouveau prompt amélioré"


def test_admin_updating_one_agent_does_not_affect_other_organizations_agents(client):
    """
    Test central de non-fuite : modifier l'agent de l'organisation A ne doit
    JAMAIS toucher un agent de même catégorie chez l'organisation B.
    """
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    admin_headers = get_super_admin_headers(client)

    req_a = client.post("/agent-requests", json={"use_case": "telecom", "objective": "A"}, headers=headers_a).json()
    req_b = client.post("/agent-requests", json={"use_case": "telecom", "objective": "B"}, headers=headers_b).json()
    result_a = client.post(f"/admin/agent-requests/{req_a['id']}/fulfill", json={"name": "Agent A", "system_prompt": "Prompt original"}, headers=admin_headers).json()
    client.post(f"/admin/agent-requests/{req_b['id']}/fulfill", json={"name": "Agent B", "system_prompt": "Prompt original"}, headers=admin_headers)

    client.patch(f"/admin/agents/{result_a['created_agent_id']}", json={"system_prompt": "Modifié uniquement pour A"}, headers=admin_headers)

    agent_b = client.get("/agents", headers=headers_b).json()[0]
    assert agent_b["system_prompt"] == "Prompt original"  # jamais touché


def test_client_cannot_use_admin_update_endpoint(client):
    headers = setup_org(client)
    admin_headers = get_super_admin_headers(client)
    req = client.post("/agent-requests", json={"use_case": "hotellerie", "objective": "Test"}, headers=headers).json()
    result = client.post(f"/admin/agent-requests/{req['id']}/fulfill", json={"name": "Agent"}, headers=admin_headers).json()

    response = client.patch(f"/admin/agents/{result['created_agent_id']}", json={"system_prompt": "Piraté"}, headers=headers)
    assert response.status_code == 403
