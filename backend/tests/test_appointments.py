"""
Tests du module Rendez-vous — cas d'usage prospection commerciale
(sections 19, 30, 41 du cahier des charges).
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent(client, headers, **overrides):
    payload = {"name": "Agent prospection"}
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def create_call_with_contact(client, headers, agent_id, contact_id):
    return client.post(
        "/calls",
        json={"agent_id": agent_id, "to_number": "+221770000000", "from_number": "+221780000000", "contact_id": contact_id},
        headers=headers,
    )


def test_appointment_auto_created_when_call_results_in_rdv(client):
    """
    Cas d'usage central : quand un appel de prospection aboutit à
    "Rendez-vous pris", un vrai rendez-vous (avec date) doit être créé
    automatiquement — pas seulement une étiquette de statut.
    """
    headers = setup_org(client)
    agent = create_agent(client, headers)
    contact = client.post("/contacts", json={"phone": "+221770000001", "first_name": "Awa"}, headers=headers).json()

    found_appointment = False
    for _ in range(60):  # "Rendez-vous pris" est une des issues possibles, pas systématique
        create_call_with_contact(client, headers, agent["id"], contact["id"])
        appointments = client.get("/appointments", headers=headers).json()
        if appointments:
            found_appointment = True
            appt = appointments[0]
            assert appt["contact_id"] == contact["id"]
            assert appt["status"] == "scheduled"
            assert appt["scheduled_at"] is not None
            break

    assert found_appointment, "Aucun rendez-vous auto-créé après 60 appels (probabilité anormalement basse)"

    # Le contact doit aussi être passé au statut RDV (section 18)
    updated_contact = client.get("/contacts", headers=headers).json()[0]
    assert updated_contact["status"] == "RDV"


def test_manual_appointment_creation(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+221770000002"}, headers=headers).json()

    response = client.post(
        "/appointments",
        json={"contact_id": contact["id"], "scheduled_at": "2026-09-01T10:00:00", "duration_minutes": 45, "notes": "Démo produit"},
        headers=headers,
    )
    assert response.status_code == 200
    appt = response.json()
    assert appt["duration_minutes"] == 45
    assert appt["status"] == "scheduled"

    # Créer un RDV manuel doit aussi mettre à jour le statut du contact
    updated_contact = client.get("/contacts", headers=headers).json()[0]
    assert updated_contact["status"] == "RDV"


def test_update_appointment_status(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+221770000003"}, headers=headers).json()
    appt = client.post(
        "/appointments",
        json={"contact_id": contact["id"], "scheduled_at": "2026-09-01T10:00:00"},
        headers=headers,
    ).json()

    response = client.patch(f"/appointments/{appt['id']}", json={"status": "confirmed"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_update_appointment_rejects_invalid_status(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+221770000004"}, headers=headers).json()
    appt = client.post(
        "/appointments",
        json={"contact_id": contact["id"], "scheduled_at": "2026-09-01T10:00:00"},
        headers=headers,
    ).json()

    response = client.patch(f"/appointments/{appt['id']}", json={"status": "n_importe_quoi"}, headers=headers)
    assert response.status_code == 400


def test_appointments_listed_in_chronological_order(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+221770000005"}, headers=headers).json()

    client.post("/appointments", json={"contact_id": contact["id"], "scheduled_at": "2026-09-05T10:00:00"}, headers=headers)
    client.post("/appointments", json={"contact_id": contact["id"], "scheduled_at": "2026-09-02T10:00:00"}, headers=headers)

    appointments = client.get("/appointments", headers=headers).json()
    assert len(appointments) == 2
    assert appointments[0]["scheduled_at"] < appointments[1]["scheduled_at"]


def test_appointments_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    contact_a = client.post("/contacts", json={"phone": "+221770000006"}, headers=headers_a).json()

    client.post("/appointments", json={"contact_id": contact_a["id"], "scheduled_at": "2026-09-01T10:00:00"}, headers=headers_a)

    appointments_b = client.get("/appointments", headers=headers_b).json()
    assert len(appointments_b) == 0


def test_cannot_create_appointment_for_contact_in_another_organization(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    contact_a = client.post("/contacts", json={"phone": "+221770000007"}, headers=headers_a).json()

    response = client.post(
        "/appointments", json={"contact_id": contact_a["id"], "scheduled_at": "2026-09-01T10:00:00"}, headers=headers_b
    )
    assert response.status_code == 404
