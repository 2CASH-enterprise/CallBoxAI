"""
Tests de la confirmation de réservation par SMS (section 12/16 du cahier
des charges), en complément de l'email.
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
    raise AssertionError("Aucune disponibilité trouvée (improbable)")


def test_dashboard_reservation_sends_sms(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612360001"}, headers=headers).json()
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
    body = response.json()
    assert body["confirmation_sms_sent"] is True

    sms_log = client.get("/sms", headers=headers).json()
    assert len(sms_log) == 1
    assert sms_log[0]["to_number"] == "+33612360001"
    assert body["pms_confirmation_number"] in sms_log[0]["body"]


def test_realtime_tool_reservation_sends_sms(client):
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
            "guest_phone": "+33612360002",
        },
    )
    body = response.json()
    assert body["confirmation_sms_sent"] is True

    sms_log = client.get("/sms", headers=headers).json()
    assert len(sms_log) == 1


def test_sms_failure_does_not_block_reservation(client):
    """Résilience (section 29) : un échec d'envoi SMS ne doit jamais empêcher la réservation."""
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612360003"}, headers=headers).json()
    check_in = find_available_date(client, headers)

    with patch("app.providers.messaging.mock.MockMessagingProvider.send_sms", side_effect=ConnectionRefusedError("panne")):
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
    assert response.json()["pms_confirmation_number"] is not None
    assert response.json()["confirmation_sms_sent"] is False


def test_sms_log_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    contact_a = client.post("/contacts", json={"phone": "+33612360004"}, headers=headers_a).json()
    check_in = find_available_date(client, headers_a)

    client.post(
        "/pms/reservations",
        json={
            "contact_id": contact_a["id"],
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
        },
        headers=headers_a,
    )

    sms_log_b = client.get("/sms", headers=headers_b).json()
    assert len(sms_log_b) == 0


@patch("app.providers.email.mock.MockEmailProvider.send")
def test_both_email_and_sms_sent_together(mock_email_send, client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612360005"}, headers=headers).json()
    check_in = find_available_date(client, headers)

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
    body = response.json()
    assert body["confirmation_email_sent"] is True
    assert body["confirmation_sms_sent"] is True
