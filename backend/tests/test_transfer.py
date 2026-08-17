"""
Tests du transfert vers un opérateur humain (sections 8, 11, 12 du cahier des charges).
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent(client, headers, **overrides):
    payload = {"name": "Agent test", "system_prompt": "Tu es un agent commercial."}
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def create_call(client, headers, agent_id):
    return client.post(
        "/calls",
        json={"agent_id": agent_id, "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers,
    )


def test_agent_transfer_fields_persisted(client):
    headers = setup_org(client)
    agent = create_agent(
        client, headers,
        transfer_enabled=True,
        transfer_number="+221339000000",
        transfer_instructions="Transférer si demande de remboursement",
    )
    assert agent["transfer_enabled"] is True
    assert agent["transfer_number"] == "+221339000000"


def test_no_automatic_transfer_when_disabled(client):
    """Sans transfert activé, aucun appel ne doit jamais être transféré automatiquement."""
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=False)

    for _ in range(15):
        response = create_call(client, headers, agent["id"])
        call = response.json()
        assert call["status"] == "completed"
        assert call["transferred_to"] is None


def test_no_automatic_transfer_without_number(client):
    """Transfert activé mais sans numéro configuré : jamais de transfert automatique."""
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=True, transfer_number=None)

    for _ in range(15):
        response = create_call(client, headers, agent["id"])
        assert response.json()["status"] == "completed"


def test_automatic_transfer_occurs_with_enabled_agent(client):
    """
    Avec le transfert activé et un numéro configuré, certains appels (mais
    pas tous) doivent être automatiquement transférés (test statistique).
    """
    headers = setup_org(client)
    agent = create_agent(
        client, headers,
        transfer_enabled=True,
        transfer_number="+221339000000",
        transfer_instructions="Demande hors compétence de l'agent",
    )

    statuses = []
    for _ in range(40):
        response = create_call(client, headers, agent["id"])
        statuses.append(response.json()["status"])

    assert "transferred" in statuses  # au moins un transfert sur 40 appels (proba 30%)
    assert "completed" in statuses  # mais pas tous

    transferred_calls = [s for s in statuses if s == "transferred"]
    assert len(transferred_calls) > 0


def test_transferred_call_has_destination_and_transcript_note(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=True, transfer_number="+221339000000")

    # Plusieurs tentatives pour obtenir un transfert (30% de chances par appel)
    transferred_call = None
    for _ in range(30):
        response = create_call(client, headers, agent["id"]).json()
        if response["status"] == "transferred":
            transferred_call = response
            break

    assert transferred_call is not None
    assert transferred_call["transferred_to"] == "+221339000000"
    assert transferred_call["transferred_at"] is not None
    assert "Transfert vers un opérateur humain" in transferred_call["transcript"]


def test_manual_transfer(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=False)  # pas besoin d'être activé pour un transfert manuel
    call = create_call(client, headers, agent["id"]).json()
    assert call["status"] == "completed"

    response = client.post(
        f"/calls/{call['id']}/transfer", json={"destination": "+221339999999"}, headers=headers
    )
    assert response.status_code == 200
    transferred = response.json()
    assert transferred["status"] == "transferred"
    assert transferred["transferred_to"] == "+221339999999"
    assert "Transfert manuel" in transferred["transcript"]


def test_manual_transfer_uses_agent_number_by_default(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=True, transfer_number="+221339000000")
    call = create_call(client, headers, agent["id"]).json()

    # Pas de destination fournie -> doit utiliser le numéro de l'agent
    response = client.post(f"/calls/{call['id']}/transfer", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["transferred_to"] == "+221339000000"


def test_manual_transfer_fails_without_any_number(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, transfer_enabled=False, transfer_number=None)
    call = create_call(client, headers, agent["id"]).json()

    response = client.post(f"/calls/{call['id']}/transfer", json={}, headers=headers)
    assert response.status_code == 400


def test_manual_transfer_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)

    agent_a = create_agent(client, headers_a)
    call_a = create_call(client, headers_a, agent_a["id"]).json()

    response = client.post(f"/calls/{call_a['id']}/transfer", json={}, headers=headers_b)
    assert response.status_code == 404
