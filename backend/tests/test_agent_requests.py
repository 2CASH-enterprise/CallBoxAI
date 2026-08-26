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
