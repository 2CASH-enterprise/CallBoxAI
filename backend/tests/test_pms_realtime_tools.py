"""
Tests des outils PMS appelés par Retell EN DIRECT pendant l'appel
(function calling, section 16 du cahier des charges).
"""
from datetime import date, timedelta
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def find_available_date(client, headers, room_type="Chambre Standard"):
    for i in range(1, 60):
        candidate = date.today() + timedelta(days=i)
        offers = client.post(
            "/pms/availability",
            json={"check_in": candidate.isoformat(), "check_out": (candidate + timedelta(days=1)).isoformat(), "room_type": room_type},
            headers=headers,
        ).json()
        if offers:
            return candidate
    raise AssertionError("Aucune disponibilité trouvée sur 60 jours (improbable)")


def test_tool_availability_works_without_jwt(client):
    """
    Point critique : Retell ne peut pas s'authentifier comme un utilisateur
    du dashboard — ce endpoint doit fonctionner sans aucun header d'auth,
    juste avec organization_id en query param.
    """
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    check_in = date.today() + timedelta(days=10)

    response = client.post(
        f"/pms/tools/availability?organization_id={org_id}",
        json={"check_in": check_in.isoformat(), "check_out": (check_in + timedelta(days=1)).isoformat()},
        # Pas de headers d'authentification du tout, volontairement.
    )
    assert response.status_code == 200
    body = response.json()
    assert "available" in body


def test_tool_reservation_creates_contact_by_phone_and_books(client):
    """
    L'agent n'a pas de contact_id du CRM pendant l'appel — seulement ce que
    dit l'appelant (nom, téléphone). Le contact doit être créé à la volée.
    """
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    check_in = find_available_date(client, headers)

    response = client.post(
        f"/pms/tools/reservations?organization_id={org_id}",
        json={
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
            "guest_name": "Jean Dupont",
            "guest_phone": "+33612345699",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["confirmation_number"].startswith("MOCK-")

    # Le contact doit avoir été créé automatiquement
    contacts = client.get("/contacts", headers=headers).json()
    assert any(c["phone"] == "+33612345699" and c["first_name"] == "Jean Dupont" for c in contacts)


def test_tool_reservation_reuses_existing_contact_by_phone(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    client.post("/contacts", json={"phone": "+33612345700", "first_name": "Déjà là"}, headers=headers)
    check_in = find_available_date(client, headers)

    client.post(
        f"/pms/tools/reservations?organization_id={org_id}",
        json={
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
            "guest_name": "Nom Différent",
            "guest_phone": "+33612345700",
        },
    )

    contacts = client.get("/contacts", headers=headers).json()
    matching = [c for c in contacts if c["phone"] == "+33612345700"]
    assert len(matching) == 1  # pas de doublon
    assert matching[0]["first_name"] == "Déjà là"  # le contact existant n'est pas écrasé


def test_tool_reservation_isolated_between_organizations(client):
    """Un outil Retell mal configuré (mauvais organization_id) ne doit jamais voir les données d'une autre organisation."""
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    org_b_id = headers_b["x-organization-id"]

    client.post("/contacts", json={"phone": "+33612345701"}, headers=headers_a)
    check_in = find_available_date(client, headers_b)

    client.post(
        f"/pms/tools/reservations?organization_id={org_b_id}",
        json={
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
            "guest_name": "Test",
            "guest_phone": "+33612345701",
        },
    )

    # Le contact créé côté B ne doit pas apparaître côté A malgré le même numéro
    contacts_a = client.get("/contacts", headers=headers_a).json()
    contacts_b = client.get("/contacts", headers=headers_b).json()
    assert len(contacts_a) == 1
    assert len(contacts_b) == 1
    assert contacts_a[0]["id"] != contacts_b[0]["id"]


def test_tool_reservation_handles_no_availability_gracefully(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]

    sold_out_date = None
    for i in range(1, 60):
        candidate = date.today() + timedelta(days=i)
        offers = client.post(
            "/pms/availability",
            json={"check_in": candidate.isoformat(), "check_out": (candidate + timedelta(days=1)).isoformat(), "room_type": "Suite"},
            headers=headers,
        ).json()
        if not offers:
            sold_out_date = candidate
            break
    assert sold_out_date is not None

    response = client.post(
        f"/pms/tools/reservations?organization_id={org_id}",
        json={
            "check_in": sold_out_date.isoformat(),
            "check_out": (sold_out_date + timedelta(days=1)).isoformat(),
            "room_type": "Suite",
            "guest_name": "Test",
            "guest_phone": "+33612345702",
        },
    )
    assert response.status_code == 200  # jamais d'erreur HTTP brute, un message clair pour le LLM
    assert response.json()["success"] is False


def test_pms_tools_registered_when_agent_has_pms_enabled(client):
    """
    Vérifie que les outils PMS sont bien transmis à Retell lors du
    provisionnement, avec l'organization_id de l'agent encodé dans l'URL.
    """
    headers = setup_org(client)
    org_id = headers["x-organization-id"]

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

            client.post("/agents", json={"name": "Réceptionniste", "pms_enabled": True}, headers=headers)

        _, kwargs = mock_create_llm.call_args
        assert "tools" in kwargs
        tool_urls = [t["url"] for t in kwargs["tools"]]
        assert any(org_id in url for url in tool_urls)
        assert any("check_room_availability" == t["name"] for t in kwargs["tools"])
        assert any("create_room_reservation" == t["name"] for t in kwargs["tools"])


def test_pms_tools_not_registered_without_public_base_url(client):
    """Sans public_base_url configuré, les outils ne doivent pas être envoyés (résilience, section 29)."""
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
            mock_settings.public_base_url = ""  # non configuré

            client.post("/agents", json={"name": "Réceptionniste", "pms_enabled": True}, headers=headers)

        _, kwargs = mock_create_llm.call_args
        assert kwargs.get("tools") is None
