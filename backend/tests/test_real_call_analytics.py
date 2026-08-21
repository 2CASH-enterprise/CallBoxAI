"""
Tests de la classification/ticket/CRM sur les VRAIS appels, complétés de
façon asynchrone via webhook (section 16/19/30 du cahier des charges) —
jusqu'ici, ce pipeline ne fonctionnait que pour les appels simulés.
"""
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent(client, headers, **overrides):
    payload = {"name": "Agent test"}
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def test_webhook_url_registered_at_provisioning(client):
    """
    Bug réel corrigé : sans webhook_url, Retell n'a aucun moyen de nous
    notifier la fin d'un appel — vérifie qu'il est bien transmis.
    """
    headers = setup_org(client)

    with patch("app.providers.voice.retell_provider.RetellProvider.create_llm") as mock_create_llm, \
         patch("app.providers.voice.retell_provider.RetellProvider.create_retell_agent") as mock_create_agent, \
         patch("app.providers.voice.retell_provider.RetellProvider.publish_agent") as mock_publish:
        mock_create_llm.return_value = {"llm_id": "llm_fake"}
        mock_create_agent.return_value = {"agent_id": "agent_fake"}
        mock_publish.return_value = {}

        with patch("app.api.routes.agents.settings") as mock_settings:
            mock_settings.voice_provider = "retell"
            mock_settings.retell_api_key = "fake_key"
            mock_settings.retell_default_llm_model = "gpt-4o-mini"
            mock_settings.retell_default_voice_id = "cartesia-Emma"
            mock_settings.public_base_url = "http://example.com"

            client.post("/agents", json={"name": "Test"}, headers=headers)

        _, kwargs = mock_create_agent.call_args
        assert kwargs["webhook_url"] == "http://example.com/webhooks/retell"


def test_web_call_test_creates_a_call_row(client):
    """
    Bug réel corrigé : le test vocal ne créait aucune ligne Call, donc rien
    à compléter même si le webhook arrivait.
    """
    headers = setup_org(client)

    with patch("app.providers.voice.retell_provider.RetellProvider.provision_agent") as mock_provision:
        mock_provision.return_value = {"agent_id": "agent_retell_fake", "llm_id": "llm_retell_fake"}
        with patch("app.api.routes.agents.settings") as mock_settings:
            mock_settings.voice_provider = "retell"
            mock_settings.retell_api_key = "fake_key"
            mock_settings.retell_default_llm_model = "gpt-4o-mini"
            mock_settings.retell_default_voice_id = "cartesia-Emma"
            agent = client.post("/agents", json={"name": "Agent"}, headers=headers).json()

    with patch("app.providers.voice.retell_provider.RetellProvider.create_web_call") as mock_web_call:
        mock_web_call.return_value = {"access_token": "token_fake", "call_id": "call_web_fake"}
        with patch("app.api.routes.agents.settings") as mock_settings:
            mock_settings.retell_api_key = "fake_key"
            mock_settings.retell_agent_id = ""
            client.post(f"/agents/{agent['id']}/test-call", headers=headers)

    calls = client.get("/calls", headers=headers).json()
    assert len(calls) == 1
    assert calls[0]["provider_call_id"] == "call_web_fake"
    assert calls[0]["status"] == "in_progress"
    assert calls[0]["provider"] == "retell"


def test_webhook_call_analyzed_triggers_classification_and_ticket(client, db_session):
    """
    Test central : un vrai appel complété via webhook doit désormais obtenir
    une classification et générer un ticket, exactement comme un appel simulé.
    """
    headers = setup_org(client)
    agent = create_agent(client, headers, ticketing_enabled=True)

    from app.models.call import Call
    import uuid as uuid_module

    provider_call_id = "call_real_fake_001"
    db_session.add(Call(
        organization_id=uuid_module.UUID(headers["x-organization-id"]),
        agent_id=uuid_module.UUID(agent["id"]),
        direction="inbound",
        status="in_progress",
        provider="retell",
        provider_call_id=provider_call_id,
    ))
    db_session.commit()

    response = client.post(
        "/webhooks/retell",
        json={
            "event": "call_analyzed",
            "call": {
                "call_id": provider_call_id,
                "transcript": "Agent: Bonjour. Client: J'ai un souci avec ma chambre.",
                "call_analysis": {"call_summary": "Réclamation concernant la chambre."},
            },
        },
    )
    assert response.status_code == 200

    calls = client.get("/calls", headers=headers).json()
    completed_call = next(c for c in calls if c["provider_call_id"] == provider_call_id)
    assert completed_call["status"] == "completed"
    assert completed_call["intent"] is not None
    assert completed_call["qualification"] is not None

    tickets = client.get("/tickets", headers=headers).json()
    assert len(tickets) == 1
    assert tickets[0]["call_id"] == completed_call["id"]


def test_webhook_analytics_idempotent_on_retry(client, db_session):
    """
    Résilience (section 29) : Retell peut retenter la livraison du webhook —
    la classification/le ticket ne doivent JAMAIS être appliqués deux fois.
    """
    headers = setup_org(client)
    agent = create_agent(client, headers, ticketing_enabled=True)

    from app.models.call import Call
    import uuid as uuid_module

    db_session.add(Call(
        organization_id=uuid_module.UUID(headers["x-organization-id"]),
        agent_id=uuid_module.UUID(agent["id"]),
        direction="inbound",
        status="in_progress",
        provider="retell",
        provider_call_id="call_retry_fake_001",
    ))
    db_session.commit()

    payload = {
        "event": "call_analyzed",
        "call": {"call_id": "call_retry_fake_001", "transcript": "Test.", "call_analysis": {"call_summary": "Résumé."}},
    }
    client.post("/webhooks/retell", json=payload)
    client.post("/webhooks/retell", json=payload)  # retry

    tickets = client.get("/tickets", headers=headers).json()
    assert len(tickets) == 1  # pas de doublon


def test_hotel_agent_real_call_does_not_create_duplicate_generic_appointment(client, db_session):
    """
    Un agent PMS ne doit jamais recevoir de rendez-vous générique en plus de
    sa vraie réservation créée par l'outil dédié pendant l'appel.
    """
    headers = setup_org(client)
    agent = create_agent(client, headers, pms_enabled=True, category="hotellerie")
    contact = client.post("/contacts", json={"phone": "+33612380002"}, headers=headers).json()

    from app.models.call import Call
    import uuid as uuid_module

    for i in range(1, 15):
        db_session.add(Call(
            organization_id=uuid_module.UUID(headers["x-organization-id"]),
            agent_id=uuid_module.UUID(agent["id"]),
            contact_id=uuid_module.UUID(contact["id"]),
            direction="inbound",
            status="in_progress",
            provider="retell",
            provider_call_id=f"call_hotel_fake_{i:03d}",
        ))
    db_session.commit()

    for i in range(1, 15):
        client.post("/webhooks/retell", json={
            "event": "call_analyzed",
            "call": {"call_id": f"call_hotel_fake_{i:03d}", "transcript": "Test.", "call_analysis": {"call_summary": "Résumé."}},
        })

    appointments = client.get("/appointments", headers=headers).json()
    # Aucun rendez-vous générique ne doit avoir été créé pour cet agent PMS
    # (aucune vraie réservation PMS n'a été faite dans ce test)
    assert len(appointments) == 0
