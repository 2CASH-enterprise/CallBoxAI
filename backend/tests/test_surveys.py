"""
Tests des sondages téléphoniques.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent(client, headers):
    return client.post("/agents", json={"name": "Agent sondage"}, headers=headers).json()


def sample_questions():
    return [
        {"id": "q1", "text": "Êtes-vous satisfait de notre service ?", "type": "choice", "options": ["Oui", "Non", "Sans avis"]},
        {"id": "q2", "text": "Note sur 5", "type": "rating"},
        {"id": "q3", "text": "Commentaire libre", "type": "open"},
    ]


def test_create_survey(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)

    response = client.post(
        "/surveys",
        json={"title": "Satisfaction client", "agent_id": agent["id"], "questions": sample_questions()},
        headers=headers,
    )
    assert response.status_code == 200
    survey = response.json()
    assert len(survey["questions"]) == 3


def test_create_survey_requires_at_least_one_question(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    response = client.post(
        "/surveys", json={"title": "Vide", "agent_id": agent["id"], "questions": []}, headers=headers
    )
    assert response.status_code == 400


def test_create_survey_choice_question_requires_options(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    response = client.post(
        "/surveys",
        json={
            "title": "Invalide",
            "agent_id": agent["id"],
            "questions": [{"id": "q1", "text": "Sans options", "type": "choice"}],
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_call_for_survey_creates_real_call_and_response(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    contact = client.post("/contacts", json={"phone": "+221770000001"}, headers=headers).json()
    survey = client.post(
        "/surveys",
        json={"title": "Satisfaction", "agent_id": agent["id"], "questions": sample_questions()},
        headers=headers,
    ).json()

    response = client.post(
        f"/surveys/{survey['id']}/call",
        json={"contact_id": contact["id"], "to_number": "+221770000001"},
        headers=headers,
    )
    assert response.status_code == 200
    survey_response = response.json()
    assert set(survey_response["answers"].keys()) == {"q1", "q2", "q3"}
    assert survey_response["answers"]["q1"] in ["Oui", "Non", "Sans avis"]
    assert 1 <= survey_response["answers"]["q2"] <= 5

    # L'appel doit apparaître normalement dans /calls (réutilisation du pipeline)
    calls = client.get("/calls", headers=headers).json()
    assert len(calls) == 1
    assert calls[0]["id"] == survey_response["call_id"]


def test_survey_results_aggregate_correctly(client):
    headers = setup_org(client)
    agent = create_agent(client, headers)
    survey = client.post(
        "/surveys",
        json={"title": "Satisfaction", "agent_id": agent["id"], "questions": sample_questions()},
        headers=headers,
    ).json()

    for i in range(10):
        contact = client.post("/contacts", json={"phone": f"+22177000{1000+i}"}, headers=headers).json()
        client.post(
            f"/surveys/{survey['id']}/call",
            json={"contact_id": contact["id"], "to_number": contact["phone"]},
            headers=headers,
        )

    results = client.get(f"/surveys/{survey['id']}/results", headers=headers).json()
    assert results["total_responses"] == 10

    q1_result = next(r for r in results["results"] if r["question_id"] == "q1")
    assert sum(q1_result["summary"].values()) == 10  # toutes les réponses comptées

    q2_result = next(r for r in results["results"] if r["question_id"] == "q2")
    assert 1 <= q2_result["summary"]["average"] <= 5
    assert q2_result["summary"]["count"] == 10

    q3_result = next(r for r in results["results"] if r["question_id"] == "q3")
    assert len(q3_result["summary"]["responses"]) == 10


def test_survey_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    agent_a = create_agent(client, headers_a)
    client.post(
        "/surveys", json={"title": "Sondage A", "agent_id": agent_a["id"], "questions": sample_questions()}, headers=headers_a
    )

    surveys_b = client.get("/surveys", headers=headers_b).json()
    assert len(surveys_b) == 0


def test_call_for_survey_rejects_unknown_contact_in_other_org(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    agent_a = create_agent(client, headers_a)
    contact_b = client.post("/contacts", json={"phone": "+221770000009"}, headers=headers_b).json()
    survey_a = client.post(
        "/surveys", json={"title": "Sondage A", "agent_id": agent_a["id"], "questions": sample_questions()}, headers=headers_a
    ).json()

    response = client.post(
        f"/surveys/{survey_a['id']}/call",
        json={"contact_id": contact_b["id"], "to_number": "+221770000009"},
        headers=headers_a,
    )
    assert response.status_code == 404
