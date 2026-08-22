"""
Tests de la collecte d'email et de l'envoi de la confirmation de réservation
(section 12/16 du cahier des charges).
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


def test_contact_email_field_persisted(client):
    headers = setup_org(client)
    response = client.post(
        "/contacts", json={"phone": "+33612340001", "first_name": "Awa", "email": "awa@example.com"}, headers=headers
    )
    assert response.json()["email"] == "awa@example.com"


def test_import_recognizes_email_column(client):
    headers = setup_org(client)
    csv_content = "phone,nom,email\n+33612340002,Client Test,client@example.com\n"
    response = client.post("/contacts/import/text", json={"content": csv_content}, headers=headers)
    assert response.json()["imported"] == 1

    contact = client.get("/contacts", headers=headers).json()[0]
    assert contact["email"] == "client@example.com"


@patch("app.providers.email.mock.MockEmailProvider.send")
def test_dashboard_reservation_sends_confirmation_email(mock_send, client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612340003"}, headers=headers).json()
    check_in = find_available_date(client, headers)

    response = client.post(
        "/pms/reservations",
        json={
            "contact_id": contact["id"],
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
            "guest_email": "reservation@example.com",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["confirmation_email_sent"] is True

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to_email"] == "reservation@example.com"
    assert body["pms_confirmation_number"] in kwargs["subject"]


@patch("app.providers.email.mock.MockEmailProvider.send")
def test_reservation_without_email_does_not_send_but_still_succeeds(mock_send, client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612340004"}, headers=headers).json()
    check_in = find_available_date(client, headers)

    response = client.post(
        "/pms/reservations",
        json={
            "contact_id": contact["id"],
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["confirmation_email_sent"] is False
    mock_send.assert_not_called()


def test_reservation_email_failure_does_not_block_reservation(client):
    """
    Résilience (section 29) : si l'envoi d'email échoue (SMTP injoignable),
    la réservation doit quand même réussir — elle est déjà actée.
    """
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612340005"}, headers=headers).json()
    check_in = find_available_date(client, headers)

    with patch("app.providers.email.mock.MockEmailProvider.send", side_effect=ConnectionRefusedError("SMTP injoignable")):
        response = client.post(
            "/pms/reservations",
            json={
                "contact_id": contact["id"],
                "check_in": check_in.isoformat(),
                "check_out": (check_in + timedelta(days=1)).isoformat(),
                "room_type": "Chambre Standard",
                "guest_email": "test@example.com",
            },
            headers=headers,
        )

    assert response.status_code == 200  # la réservation réussit quand même
    assert response.json()["pms_confirmation_number"] is not None
    assert response.json()["confirmation_email_sent"] is False  # mais l'email a bien échoué


@patch("app.providers.email.mock.MockEmailProvider.send")
def test_realtime_tool_reservation_collects_and_uses_email(mock_send, client):
    """L'outil appelé par Retell pendant l'appel doit aussi gérer l'email."""
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
            "guest_phone": "+33612340006",
            "guest_email": "jean.dupont@example.com",
        },
    )
    body = response.json()
    assert body["success"] is True
    assert body["confirmation_email_sent"] is True

    contacts = client.get("/contacts", headers=headers).json()
    assert any(c["email"] == "jean.dupont@example.com" for c in contacts)


@patch("app.providers.email.mock.MockEmailProvider.send")
def test_realtime_tool_reservation_works_without_email(mock_send, client):
    """Le client peut refuser de donner son email — la réservation doit quand même fonctionner."""
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    check_in = find_available_date(client, headers)

    response = client.post(
        f"/pms/tools/reservations?organization_id={org_id}",
        json={
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
            "guest_name": "Anonyme",
            "guest_phone": "+33612340007",
        },
    )
    body = response.json()
    assert body["success"] is True
    assert body["confirmation_email_sent"] is False
    mock_send.assert_not_called()


def test_pms_tool_schema_includes_email_parameter():
    """Vérifie que l'outil Retell demande bien l'email (pas seulement nom/téléphone)."""
    from app.providers.voice.retell_provider import _build_pms_tools

    tools = _build_pms_tools("org-fake", "http://example.com")
    reservation_tool = next(t for t in tools if t["name"] == "create_room_reservation")
    assert "guest_email" in reservation_tool["parameters"]["properties"]
    # Optionnel : ne doit pas être dans "required" (le client peut refuser)
    assert "guest_email" not in reservation_tool["parameters"]["required"]


@patch("app.providers.email.mock.MockEmailProvider.send")
def test_confirmation_email_includes_hotel_name_and_html(mock_send, client, db_session):
    """
    L'email de confirmation doit être personnalisé au nom de l'établissement
    (Organization.name), avec une version HTML soignée en plus du texte brut
    — pas la marque blanche des distributeurs, qui concerne le dashboard.
    """
    headers = setup_org(client)
    # Renomme l'organisation pour vérifier que le nom apparaît bien dans l'email
    from app.models.organization import Organization
    import uuid as uuid_module

    org = db_session.query(Organization).filter(Organization.id == uuid_module.UUID(headers["x-organization-id"])).first()
    org.name = "Hôtel Le Test Suprême"
    db_session.commit()

    contact = client.post("/contacts", json={"phone": "+33612370010"}, headers=headers).json()
    check_in = find_available_date(client, headers)

    client.post(
        "/pms/reservations",
        json={
            "contact_id": contact["id"],
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
            "guest_email": "verif@example.com",
        },
        headers=headers,
    )

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert "Hôtel Le Test Suprême" in kwargs["body"]
    assert kwargs["html_body"] is not None
    assert "Hôtel Le Test Suprême" in kwargs["html_body"]
    assert "<html" in kwargs["html_body"]
    assert "MOCK-" in kwargs["html_body"]  # numéro de confirmation présent dans le HTML
