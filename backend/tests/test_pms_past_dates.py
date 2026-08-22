"""
Rejet des dates passées pour une réservation hôtelière (bug réel signalé :
l'agent confirmait une réservation pour une date déjà passée).
"""
from datetime import date, timedelta

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_availability_rejects_past_check_in_dashboard(client):
    headers = setup_org(client)
    past_date = date.today() - timedelta(days=5)

    response = client.post(
        "/pms/availability",
        json={"check_in": past_date.isoformat(), "check_out": (past_date + timedelta(days=1)).isoformat()},
        headers=headers,
    )
    assert response.status_code == 400
    assert "passé" in response.json()["detail"]


def test_availability_rejects_past_check_in_realtime_tool(client):
    """C'est ce chemin précis qu'utilise l'agent vocal en direct pendant l'appel."""
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    past_date = date.today() - timedelta(days=5)

    response = client.post(
        f"/pms/tools/availability?organization_id={org_id}",
        json={"check_in": past_date.isoformat(), "check_out": (past_date + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 200  # jamais d'erreur HTTP brute pour l'agent, un message clair
    body = response.json()
    assert body["available"] is False
    assert "passé" in body["error"]


def test_reservation_rejects_past_check_in_realtime_tool(client):
    """Test central : reproduit exactement le bug signalé — plus de confirmation pour une date passée."""
    headers = setup_org(client)
    org_id = headers["x-organization-id"]
    past_date = date.today() - timedelta(days=5)

    response = client.post(
        f"/pms/tools/reservations?organization_id={org_id}",
        json={
            "check_in": past_date.isoformat(),
            "check_out": (past_date + timedelta(days=1)).isoformat(),
            "room_type": "Chambre Standard",
            "guest_name": "Test",
            "guest_phone": "+33612400001",
        },
    )
    body = response.json()
    assert body["success"] is False
    assert "passé" in body["error"]

    # Aucune réservation ne doit avoir été créée
    appointments = client.get("/appointments", headers=headers).json()
    assert len(appointments) == 0


def test_today_is_accepted_as_check_in(client):
    """Aujourd'hui même reste une date valide (seul le passé est rejeté)."""
    headers = setup_org(client)
    today = date.today()

    response = client.post(
        "/pms/availability",
        json={"check_in": today.isoformat(), "check_out": (today + timedelta(days=1)).isoformat()},
        headers=headers,
    )
    assert response.status_code == 200  # accepté (peut retourner une liste vide selon la dispo, mais pas d'erreur)


def test_future_dates_still_work_normally(client):
    headers = setup_org(client)
    future = date.today() + timedelta(days=10)

    response = client.post(
        "/pms/availability",
        json={"check_in": future.isoformat(), "check_out": (future + timedelta(days=1)).isoformat()},
        headers=headers,
    )
    assert response.status_code == 200
