"""
Tests des analytics avancés (section 19 du cahier des charges) : intent,
sentiment, qualification, score, et mise à jour automatique du CRM.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent(client, headers, **overrides):
    payload = {"name": "Agent test", "system_prompt": "Tu es un agent commercial."}
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def create_call(client, headers, agent_id, contact_id=None):
    body = {"agent_id": agent_id, "to_number": "+221770000000", "from_number": "+221780000000"}
    if contact_id:
        body["contact_id"] = contact_id
    return client.post("/calls", json=body, headers=headers)


def test_call_receives_classification_fields(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    call = create_call(client, headers, agent["id"]).json()

    assert call["intent"] is not None
    assert call["qualification"] is not None
    assert call["sentiment"] in ("Positif", "Neutre", "Négatif")
    assert 0 <= call["score"] <= 100
    assert call["action_taken"] is not None


def test_transferred_call_classification_is_deterministic(client):
    """Un appel transféré doit toujours recevoir la même classification cohérente."""
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=True, transfer_number="+221339000000")

    transferred_call = None
    for _ in range(30):
        call = create_call(client, headers, agent["id"]).json()
        if call["status"] == "transferred":
            transferred_call = call
            break

    assert transferred_call is not None
    assert transferred_call["qualification"] == "À suivre par un humain"
    assert transferred_call["action_taken"] == "Transfert vers opérateur"
    assert transferred_call["score"] == 50


def test_call_with_contact_updates_crm_status(client):
    """Critère section 18 : chaque appel doit pouvoir modifier automatiquement le statut du contact."""
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=True, transfer_number="+221339000000")
    contact = client.post("/contacts", json={"phone": "+221770000001"}, headers=headers).json()
    assert contact["status"] == "Nouveau"

    # On force un transfert (déterministe : toujours "À rappeler" en résultat)
    transferred = False
    for _ in range(30):
        call = create_call(client, headers, agent["id"], contact_id=contact["id"]).json()
        if call["status"] == "transferred":
            transferred = True
            break

    assert transferred
    updated_contact = client.get("/contacts", headers=headers).json()[0]
    assert updated_contact["status"] == "À rappeler"


def test_manual_transfer_also_updates_crm_status(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=False)
    contact = client.post("/contacts", json={"phone": "+221770000002"}, headers=headers).json()
    call = create_call(client, headers, agent["id"], contact_id=contact["id"]).json()

    client.post(f"/calls/{call['id']}/transfer", json={"destination": "+221339999999"}, headers=headers)

    updated_contact = client.get("/contacts", headers=headers).json()[0]
    assert updated_contact["status"] == "À rappeler"


def test_analytics_summary_aggregates_calls(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)

    for _ in range(10):
        create_call(client, headers, agent["id"])

    summary = client.get("/analytics/summary", headers=headers).json()
    assert summary["total_calls"] == 10
    assert summary["avg_score"] is not None
    assert 0 <= summary["qualification_rate"] <= 100

    total_by_intent = sum(item["count"] for item in summary["by_intent"])
    assert total_by_intent == 10

    total_by_sentiment = sum(item["count"] for item in summary["by_sentiment"])
    assert total_by_sentiment == 10

    assert len(summary["by_agent"]) == 1
    assert summary["by_agent"][0]["calls_count"] == 10


def test_analytics_summary_empty_organization(client):
    headers = setup_org(client)
    summary = client.get("/analytics/summary", headers=headers).json()
    assert summary["total_calls"] == 0
    assert summary["avg_score"] is None
    assert summary["qualification_rate"] == 0.0
    assert summary["by_intent"] == []


def test_analytics_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)

    agent_a = create_agent(client, headers_a)
    create_call(client, headers_a, agent_a["id"])

    summary_b = client.get("/analytics/summary", headers=headers_b).json()
    assert summary_b["total_calls"] == 0


def test_campaign_batch_calls_are_also_classified(client):
    """Le pipeline partagé doit s'appliquer aussi aux appels de campagne (section 13/19)."""
    import io

    headers = setup_org(client)
    agent = create_agent(client, headers)
    campaign = client.post(
        "/campaigns",
        json={"name": "Test", "agent_id": agent["id"], "schedule_start": "00:00", "schedule_end": "23:59", "max_attempts": 3},
        headers=headers,
    ).json()

    csv_content = "phone\n" + "\n".join(f"+22177002{i:04d}" for i in range(20))
    files = {"file": ("contacts.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    client.post(f"/campaigns/{campaign['id']}/import", headers=headers, files=files)
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)
    client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers)

    calls = client.get("/calls", headers=headers).json()
    assert len(calls) > 0
    for call in calls:
        assert call["intent"] is not None
        assert call["sentiment"] is not None
