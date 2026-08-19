"""
Tests de l'intégration PMS (Property Management System — section 16 du
cahier des charges) : disponibilité, réservation, annulation.
"""
from datetime import date, timedelta

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_check_availability_returns_offers(client):
    headers = setup_org(client)
    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=2)

    response = client.post(
        "/pms/availability",
        json={"check_in": check_in.isoformat(), "check_out": check_out.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200
    offers = response.json()
    # Au moins un type de chambre disponible (catalogue de démo à 3 types)
    assert isinstance(offers, list)
    for offer in offers:
        assert offer["rooms_available"] > 0
        assert offer["total_price"] == offer["rate_per_night"] * 2  # 2 nuits


def test_check_availability_is_deterministic(client):
    """Même demande = même résultat (pas un vrai tirage aléatoire)."""
    headers = setup_org(client)
    check_in = date.today() + timedelta(days=15)
    check_out = check_in + timedelta(days=1)
    payload = {"check_in": check_in.isoformat(), "check_out": check_out.isoformat()}

    first = client.post("/pms/availability", json=payload, headers=headers).json()
    second = client.post("/pms/availability", json=payload, headers=headers).json()
    assert first == second


def test_check_availability_rejects_invalid_dates(client):
    headers = setup_org(client)
    check_in = date.today() + timedelta(days=10)
    check_out = check_in  # même jour -> 0 nuit, invalide

    response = client.post(
        "/pms/availability",
        json={"check_in": check_in.isoformat(), "check_out": check_out.isoformat()},
        headers=headers,
    )
    assert response.status_code == 400


def test_check_availability_filters_by_room_type(client):
    headers = setup_org(client)
    check_in = date.today() + timedelta(days=20)
    check_out = check_in + timedelta(days=1)

    response = client.post(
        "/pms/availability",
        json={"check_in": check_in.isoformat(), "check_out": check_out.isoformat(), "room_type": "Suite"},
        headers=headers,
    )
    offers = response.json()
    assert all(o["room_type"] == "Suite" for o in offers)


def test_create_reservation_creates_appointment(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612345678", "first_name": "Jean"}, headers=headers).json()

    # Trouve une date avec de la disponibilité pour "Chambre Standard"
    check_in = None
    for i in range(1, 60):
        candidate = date.today() + timedelta(days=i)
        offers = client.post(
            "/pms/availability",
            json={"check_in": candidate.isoformat(), "check_out": (candidate + timedelta(days=1)).isoformat(), "room_type": "Chambre Standard"},
            headers=headers,
        ).json()
        if offers:
            check_in = candidate
            break
    assert check_in is not None, "Aucune disponibilité trouvée sur 60 jours (improbable)"
    check_out = check_in + timedelta(days=1)

    response = client.post(
        "/pms/reservations",
        json={
            "contact_id": contact["id"],
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "room_type": "Chambre Standard",
        },
        headers=headers,
    )
    assert response.status_code == 200
    reservation = response.json()
    assert reservation["pms_confirmation_number"].startswith("MOCK-")
    assert reservation["status"] == "confirmed"

    # Doit apparaître dans /appointments avec les bons champs PMS
    appointments = client.get("/appointments", headers=headers).json()
    assert len(appointments) == 1
    assert appointments[0]["room_type"] == "Chambre Standard"
    assert appointments[0]["pms_confirmation_number"] == reservation["pms_confirmation_number"]

    # Le contact doit passer en statut RDV
    updated_contact = client.get("/contacts", headers=headers).json()[0]
    assert updated_contact["status"] == "RDV"


def test_create_reservation_fails_without_availability(client):
    """Sur 60 jours, au moins une date doit être complète pour "Suite" (seulement 2 chambres)."""
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612345679"}, headers=headers).json()

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
    assert sold_out_date is not None, "Aucune date complète trouvée sur 60 jours (improbable)"

    response = client.post(
        "/pms/reservations",
        json={
            "contact_id": contact["id"],
            "check_in": sold_out_date.isoformat(),
            "check_out": (sold_out_date + timedelta(days=1)).isoformat(),
            "room_type": "Suite",
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_create_reservation_rejects_unknown_contact(client):
    headers = setup_org(client)
    check_in = date.today() + timedelta(days=5)
    response = client.post(
        "/pms/reservations",
        json={
            "contact_id": "00000000-0000-0000-0000-000000000000",
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
        },
        headers=headers,
    )
    assert response.status_code == 404


def test_cancel_reservation_updates_appointment_status(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612345680"}, headers=headers).json()
    check_in = date.today() + timedelta(days=3)

    reservation = client.post(
        "/pms/reservations",
        json={
            "contact_id": contact["id"],
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
        },
        headers=headers,
    ).json()

    response = client.patch(f"/appointments/{reservation['id']}", json={"status": "cancelled"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_pms_endpoints_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    contact_a = client.post("/contacts", json={"phone": "+33612345681"}, headers=headers_a).json()

    check_in = date.today() + timedelta(days=5)
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

    # B ne doit pas pouvoir réserver pour un contact de A
    response = client.post(
        "/pms/reservations",
        json={
            "contact_id": contact_a["id"],
            "check_in": check_in.isoformat(),
            "check_out": (check_in + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
        },
        headers=headers_b,
    )
    assert response.status_code == 404

    appointments_b = client.get("/appointments", headers=headers_b).json()
    assert len(appointments_b) == 0
