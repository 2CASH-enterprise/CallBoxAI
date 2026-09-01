"""
Tests des équipes d'agents (section 40 — palier "Growth", "Employé IA") :
regroupement librement composé par le client, résumé combiné.
"""
from datetime import datetime, timedelta

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_create_and_list_team(client):
    headers = setup_org(client)
    team = client.post("/agent-teams", json={"name": "Mon équipe commerciale"}, headers=headers).json()
    assert team["name"] == "Mon équipe commerciale"
    assert team["agent_ids"] == []

    teams = client.get("/agent-teams", headers=headers).json()
    assert len(teams) == 1


def test_rename_team(client):
    headers = setup_org(client)
    team = client.post("/agent-teams", json={"name": "Ancien nom"}, headers=headers).json()

    response = client.patch(f"/agent-teams/{team['id']}", json={"name": "Nouveau nom"}, headers=headers)
    assert response.json()["name"] == "Nouveau nom"


def test_add_and_remove_agent_from_team(client):
    headers = setup_org(client)
    team = client.post("/agent-teams", json={"name": "Équipe test"}, headers=headers).json()
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    added = client.post(f"/agent-teams/{team['id']}/agents", json={"agent_id": agent["id"]}, headers=headers).json()
    assert agent["id"] in added["agent_ids"]

    agent_refreshed = client.get("/agents", headers=headers).json()[0]
    assert agent_refreshed["team_id"] == team["id"]

    removed = client.delete(f"/agent-teams/{team['id']}/agents/{agent['id']}", headers=headers).json()
    assert agent["id"] not in removed["agent_ids"]


def test_delete_team_detaches_agents_without_deleting_them(client):
    headers = setup_org(client)
    team = client.post("/agent-teams", json={"name": "Équipe éphémère"}, headers=headers).json()
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    client.post(f"/agent-teams/{team['id']}/agents", json={"agent_id": agent["id"]}, headers=headers)

    client.delete(f"/agent-teams/{team['id']}", headers=headers)

    agents = client.get("/agents", headers=headers).json()
    assert len(agents) == 1  # l'agent existe toujours
    assert agents[0]["team_id"] is None  # juste détaché


def test_teams_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    client.post("/agent-teams", json={"name": "Équipe A"}, headers=headers_a)

    teams_b = client.get("/agent-teams", headers=headers_b).json()
    assert len(teams_b) == 0


def test_cannot_add_agent_from_another_organization_to_team(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    team_a = client.post("/agent-teams", json={"name": "Équipe A"}, headers=headers_a).json()
    agent_b = client.post("/agents", json={"name": "Agent B"}, headers=headers_b).json()

    response = client.post(f"/agent-teams/{team_a['id']}/agents", json={"agent_id": agent_b["id"]}, headers=headers_a)
    assert response.status_code == 404


# ---------- Résumé combiné ----------

def test_team_summary_combines_stats_across_all_member_agents(client, db_session):
    """Test central : le résumé doit combiner les chiffres de PLUSIEURS agents, sans distinction."""
    from app.models.agent import Agent
    from app.models.call import Call
    from app.models.whatsapp_log import WhatsAppLog
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    team = client.post("/agent-teams", json={"name": "Équipe combinée"}, headers=headers).json()

    agent_a = client.post("/agents", json={"name": "Agent A"}, headers=headers).json()
    agent_b = client.post("/agents", json={"name": "Agent B"}, headers=headers).json()
    client.post(f"/agent-teams/{team['id']}/agents", json={"agent_id": agent_a["id"]}, headers=headers)
    client.post(f"/agent-teams/{team['id']}/agents", json={"agent_id": agent_b["id"]}, headers=headers)

    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent_a["id"]), direction="inbound", status="completed", provider="retell", duration_seconds=120))
    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent_b["id"]), direction="inbound", status="completed", provider="retell", duration_seconds=180))
    db_session.add(WhatsAppLog(organization_id=org_id, agent_id=uuid_module.UUID(agent_a["id"]), to_number="+221770000001", body="Test"))
    db_session.commit()

    summary = client.get(f"/agent-teams/{team['id']}/summary", headers=headers).json()
    assert summary["total_calls"] == 2
    assert summary["total_call_minutes"] == 5  # (120 + 180) / 60
    assert summary["total_whatsapp_messages"] == 1


def test_team_summary_excludes_calls_from_agents_outside_the_team(client, db_session):
    """Un agent qui n'appartient PAS à l'équipe ne doit jamais polluer son résumé."""
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    team = client.post("/agent-teams", json={"name": "Équipe restreinte"}, headers=headers).json()

    agent_in_team = client.post("/agents", json={"name": "Dans l'équipe"}, headers=headers).json()
    agent_outside = client.post("/agents", json={"name": "Hors équipe"}, headers=headers).json()
    client.post(f"/agent-teams/{team['id']}/agents", json={"agent_id": agent_in_team["id"]}, headers=headers)

    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent_in_team["id"]), direction="inbound", status="completed", provider="retell", duration_seconds=60))
    db_session.add(Call(organization_id=org_id, agent_id=uuid_module.UUID(agent_outside["id"]), direction="inbound", status="completed", provider="retell", duration_seconds=600))
    db_session.commit()

    summary = client.get(f"/agent-teams/{team['id']}/summary", headers=headers).json()
    assert summary["total_calls"] == 1
    assert summary["total_call_minutes"] == 1  # seulement l'agent de l'équipe (60s), pas les 600s de l'autre


def test_team_summary_empty_team_returns_zeros_not_error(client):
    headers = setup_org(client)
    team = client.post("/agent-teams", json={"name": "Équipe vide"}, headers=headers).json()

    summary = client.get(f"/agent-teams/{team['id']}/summary", headers=headers).json()
    assert summary["total_calls"] == 0
    assert summary["total_whatsapp_messages"] == 0


# ---------- Attribution WhatsApp par agent (correctif) ----------

def test_whatsapp_tool_now_attributes_message_to_correct_agent(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent Prospection"}, headers=headers).json()

    client.post(
        f"/prospection/tools/send-whatsapp?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+221770000002", "content_summary": "Test"},
    )

    from app.models.whatsapp_log import WhatsAppLog
    # Vérifié indirectement via le résumé d'équipe : si agent_id n'était pas
    # enregistré, le résumé combiné ne pourrait jamais isoler cette donnée.
    team = client.post("/agent-teams", json={"name": "Équipe vérif"}, headers=headers).json()
    client.post(f"/agent-teams/{team['id']}/agents", json={"agent_id": agent["id"]}, headers=headers)
    summary = client.get(f"/agent-teams/{team['id']}/summary", headers=headers).json()
    assert summary["total_whatsapp_messages"] == 1
