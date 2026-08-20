"""
Tests de la modification/annulation de réservation EN DIRECT pendant
l'appel réel (section 16 du cahier des charges).
"""
from datetime import date, timedelta

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def find_available_date(client, headers, room_type="Chambre Standard", exclude=None):
    exclude = exclude or set()
    for i in range(1, 90):
        candidate = date.today() + timedelta(days=i)
        if candidate in exclude:
            continue
        offers = client.post(
            "/pms/availability",
            json={"check_in": candidate.isoformat(), "check_out": (candidate + timedelta(days=1)).isoformat(), "room_type": room_type},
            headers=headers,
        ).json()
        if offers:
            return candidate
    raise AssertionError("Aucune disponibilité trouvée (improbable)")


def make_reservation(client, headers, org_id, phone="+33612350001"):
    check_in = find_available_date(client, headers)
    response = client.post(
        f"/pms/tools/reservations?organization_id={org_id}",
        json={
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
            "guest_name": "Test Client",
            "guest_phone": phone,
        },
    )
    return response.json(), check_in


def test_find_reservation_by_phone(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    reservation, check_in = make_reservation(client, headers, org_id)

    response = client.post(
        f"/pms/tools/find-reservation?organization_id={org_id}",
        json={"guest_phone": "+33612350001"},
    )
    body = response.json()
    assert body["found"] is True
    assert body["reservations"][0]["confirmation_number"] == reservation["confirmation_number"]
    assert body["reservations"][0]["check_in"] == check_in.isoformat()


def test_find_reservation_by_confirmation_number(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    reservation, _ = make_reservation(client, headers, org_id, phone="+33612350002")

    response = client.post(
        f"/pms/tools/find-reservation?organization_id={org_id}",
        json={"guest_phone": "numero-oublie", "confirmation_number": reservation["confirmation_number"]},
    )
    body = response.json()
    assert body["found"] is True
    assert len(body["reservations"]) == 1


def test_find_reservation_returns_not_found_gracefully(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]

    response = client.post(
        f"/pms/tools/find-reservation?organization_id={org_id}",
        json={"guest_phone": "+33600000000"},
    )
    assert response.status_code == 200
    assert response.json()["found"] is False


def test_modify_reservation_updates_dates(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    reservation, original_check_in = make_reservation(client, headers, org_id, phone="+33612350003")
    new_check_in = find_available_date(client, headers, exclude={original_check_in})

    response = client.post(
        f"/pms/tools/modify-reservation?organization_id={org_id}",
        json={
            "confirmation_number": reservation["confirmation_number"],
            "new_check_in": new_check_in.isoformat(),
            "new_check_out": (new_check_in + timedelta(days=1)).isoformat(),
        },
    )
    body = response.json()
    assert body["success"] is True
    assert body["check_in"] == new_check_in.isoformat()

    # Vérifie que la modification est bien reflétée dans /appointments
    appointments = client.get("/appointments", headers=headers).json()
    assert appointments[0]["scheduled_at"].startswith(new_check_in.isoformat())


def test_modify_reservation_keeps_unspecified_fields_unchanged(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    reservation, original_check_in = make_reservation(client, headers, org_id, phone="+33612350004")

    response = client.post(
        f"/pms/tools/modify-reservation?organization_id={org_id}",
        json={"confirmation_number": reservation["confirmation_number"]},  # rien à changer
    )
    body = response.json()
    assert body["success"] is True
    assert body["check_in"] == original_check_in.isoformat()
    assert body["room_type"] == "Chambre Standard"


def test_modify_reservation_fails_gracefully_when_not_found(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]

    response = client.post(
        f"/pms/tools/modify-reservation?organization_id={org_id}",
        json={"confirmation_number": "MOCK-INEXISTANT"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is False


def test_cancel_reservation_via_tool(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    reservation, _ = make_reservation(client, headers, org_id, phone="+33612350005")

    response = client.post(
        f"/pms/tools/cancel-reservation?organization_id={org_id}",
        json={"confirmation_number": reservation["confirmation_number"]},
    )
    assert response.json()["success"] is True

    appointments = client.get("/appointments", headers=headers).json()
    assert appointments[0]["status"] == "cancelled"


def test_cancel_already_cancelled_reservation_is_idempotent(client):
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    reservation, _ = make_reservation(client, headers, org_id, phone="+33612350006")

    client.post(f"/pms/tools/cancel-reservation?organization_id={org_id}", json={"confirmation_number": reservation["confirmation_number"]})
    second_response = client.post(f"/pms/tools/cancel-reservation?organization_id={org_id}", json={"confirmation_number": reservation["confirmation_number"]})

    assert second_response.json()["already_cancelled"] is True


def test_modify_and_cancel_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    org_a_id = headers_a["x-organization-id"]
    org_b_id = headers_b["x-organization-id"]
    reservation, _ = make_reservation(client, headers_a, org_a_id, phone="+33612350007")

    # B ne doit pas pouvoir modifier/annuler une réservation de A
    modify_response = client.post(
        f"/pms/tools/modify-reservation?organization_id={org_b_id}",
        json={"confirmation_number": reservation["confirmation_number"], "new_room_type": "Suite"},
    )
    assert modify_response.json()["success"] is False

    cancel_response = client.post(
        f"/pms/tools/cancel-reservation?organization_id={org_b_id}",
        json={"confirmation_number": reservation["confirmation_number"]},
    )
    assert cancel_response.json()["success"] is False

    # La réservation de A doit être intacte
    appointments_a = client.get("/appointments", headers=headers_a).json()
    assert appointments_a[0]["status"] == "confirmed"


def test_pms_tools_include_modify_and_cancel_definitions():
    from app.providers.voice.retell_provider import _build_pms_tools

    tools = _build_pms_tools("org-fake", "http://example.com")
    names = {t["name"] for t in tools}
    assert {"check_room_availability", "create_room_reservation", "find_reservation", "modify_reservation", "cancel_reservation"} == names
