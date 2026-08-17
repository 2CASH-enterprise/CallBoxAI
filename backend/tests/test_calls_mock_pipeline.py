"""
Vérifie le pipeline complet d'appel en mode Mock (section 40.3) :
appel -> agent IA -> transcript -> résumé -> enregistrement en base.
Aucun compte Twilio/Retell n'est nécessaire pour que ce test passe.
"""
from tests.conftest import auth_headers, register_user


def test_full_call_pipeline_with_mock_providers(client):
    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}

    agent = client.post(
        "/agents",
        json={"name": "Agent commercial", "system_prompt": "Tu es un agent commercial."},
        headers=headers,
    ).json()

    response = client.post(
        "/calls",
        json={
            "agent_id": agent["id"],
            "to_number": "+221770000000",
            "from_number": "+221780000000",
            "direction": "outbound",
        },
        headers=headers,
    )

    assert response.status_code == 200
    call = response.json()
    assert call["status"] == "completed"
    assert call["provider"] == "mock"
    assert call["transcript"] is not None
    assert call["summary"] is not None

    calls_list = client.get("/calls", headers=headers).json()
    assert len(calls_list) == 1


def test_call_rejected_for_unknown_agent_in_organization(client):
    token_a, org_a_id = register_user(client, org_name="Entreprise A")
    token_b, org_b_id = register_user(client, org_name="Entreprise B")

    agent_a = client.post(
        "/agents",
        json={"name": "Agent A"},
        headers={**auth_headers(token_a), "x-organization-id": org_a_id},
    ).json()

    # Entreprise B (avec un token valide et membre de B) tente d'utiliser un
    # agent qui appartient à Entreprise A -> refusé
    response = client.post(
        "/calls",
        json={
            "agent_id": agent_a["id"],
            "to_number": "+221770000000",
            "from_number": "+221780000000",
        },
        headers={**auth_headers(token_b), "x-organization-id": org_b_id},
    )
    assert response.status_code == 404
