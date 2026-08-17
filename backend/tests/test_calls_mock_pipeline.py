"""
Vérifie le pipeline complet d'appel en mode Mock (section 40.3) :
appel -> agent IA -> transcript -> résumé -> enregistrement en base.
Aucun compte Twilio/Retell n'est nécessaire pour que ce test passe.
"""


def test_full_call_pipeline_with_mock_providers(client):
    org = client.post("/organizations", json={"name": "Entreprise Test"}).json()
    org_id = org["id"]

    agent = client.post(
        "/agents",
        json={"name": "Agent commercial", "system_prompt": "Tu es un agent commercial."},
        headers={"x-organization-id": org_id},
    ).json()

    response = client.post(
        "/calls",
        json={
            "agent_id": agent["id"],
            "to_number": "+221770000000",
            "from_number": "+221780000000",
            "direction": "outbound",
        },
        headers={"x-organization-id": org_id},
    )

    assert response.status_code == 200
    call = response.json()
    assert call["status"] == "completed"
    assert call["provider"] == "mock"
    assert call["transcript"] is not None
    assert call["summary"] is not None

    # Vérifie que l'appel apparait bien dans le dashboard de l'entreprise
    calls_list = client.get("/calls", headers={"x-organization-id": org_id}).json()
    assert len(calls_list) == 1


def test_call_rejected_for_unknown_agent_in_organization(client):
    org_a = client.post("/organizations", json={"name": "Entreprise A"}).json()
    org_b = client.post("/organizations", json={"name": "Entreprise B"}).json()

    agent_a = client.post(
        "/agents",
        json={"name": "Agent A"},
        headers={"x-organization-id": org_a["id"]},
    ).json()

    # Entreprise B tente d'utiliser un agent qui appartient à Entreprise A -> refusé
    response = client.post(
        "/calls",
        json={
            "agent_id": agent_a["id"],
            "to_number": "+221770000000",
            "from_number": "+221780000000",
        },
        headers={"x-organization-id": org_b["id"]},
    )
    assert response.status_code == 404
