"""
Tests de l'enrichissement des rendez-vous pour l'affichage calendrier
(section 42 du cahier des charges) : nom/téléphone du contact et
qualification de l'appel associé, pour le code couleur par statut.
"""
from datetime import datetime, timedelta

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_appointment_includes_contact_name_and_phone(client):
    headers = setup_org(client)
    contact = client.post(
        "/contacts", json={"phone": "+33612600001", "first_name": "Jean", "last_name": "Dupont"}, headers=headers
    ).json()

    appointment = client.post(
        "/appointments",
        json={"contact_id": contact["id"], "scheduled_at": (datetime.utcnow() + timedelta(days=1)).isoformat()},
        headers=headers,
    ).json()

    assert appointment["contact_name"] == "Jean Dupont"
    assert appointment["contact_phone"] == "+33612600001"


def test_appointment_falls_back_to_phone_when_no_name(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612600002"}, headers=headers).json()

    appointment = client.post(
        "/appointments",
        json={"contact_id": contact["id"], "scheduled_at": (datetime.utcnow() + timedelta(days=1)).isoformat()},
        headers=headers,
    ).json()

    assert appointment["contact_name"] == "+33612600002"


def test_meeting_booked_via_tool_includes_qualification_after_call_analyzed(client, db_session):
    """
    Test central : un RDV créé via l'outil de prospection B2B, une fois
    l'appel classifié, doit exposer la qualification (pour le code couleur
    du calendrier) sans requête supplémentaire.
    """
    from app.models.agent import Agent
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    agent = client.post("/agents", json={"name": "Agent B2B"}, headers=headers).json()

    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.retell_agent_id = "retell_agent_calendar_test"
    db_session.commit()

    call_data = {
        "call_id": "call_calendar_test_001",
        "agent_id": "retell_agent_calendar_test",
        "direction": "inbound",
        "from_number": "+33612600003",
    }
    client.post("/webhooks/retell", json={"event": "call_started", "call": call_data})

    slot = (datetime.utcnow() + timedelta(days=2)).replace(microsecond=0).isoformat()
    book_response = client.post(
        f"/prospection/tools/book-meeting?organization_id={org_id}&agent_id={agent['id']}",
        json={"guest_phone": "+33612600003", "scheduled_at": slot},
    )
    assert book_response.json()["success"] is True

    # Associe manuellement l'appel au rendez-vous (dans un vrai scénario,
    # ce serait fait par le pipeline post-appel — ici on isole le test sur
    # l'enrichissement lui-même)
    from app.models.appointment import Appointment

    appt = db_session.query(Appointment).filter(Appointment.organization_id == uuid_module.UUID(org_id)).first()
    call = db_session.query(Call).filter(Call.provider_call_id == "call_calendar_test_001").first()
    appt.call_id = call.id
    call.qualification = "Prospect chaud"
    db_session.commit()

    appointments = client.get("/appointments", headers=headers).json()
    assert appointments[0]["qualification"] == "Prospect chaud"


def test_appointment_without_call_has_no_qualification(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612600004"}, headers=headers).json()

    appointment = client.post(
        "/appointments",
        json={"contact_id": contact["id"], "scheduled_at": (datetime.utcnow() + timedelta(days=1)).isoformat()},
        headers=headers,
    ).json()

    assert appointment["qualification"] is None
