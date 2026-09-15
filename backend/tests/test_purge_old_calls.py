"""
Tests de la purge automatique des appels après 6 mois (section 42/43,
recommandation CNIL).
"""
from datetime import datetime, timedelta

from app.core.purge_old_calls import run_purge, PURGE_PLACEHOLDER
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def get_super_admin_headers(client):
    response = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "superadmin-purge@example.com", "password": "TestPassword123", "full_name": "Admin Test"},
    )
    token = response.json()["access_token"]
    return auth_headers(token)


def test_purge_redacts_calls_older_than_6_months(client, db_session):
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    old_call = Call(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="inbound", status="completed",
        provider="retell", transcript="Contenu ancien à purger", summary="Résumé ancien",
        started_at=datetime.utcnow() - timedelta(days=200),  # plus de 6 mois
    )
    db_session.add(old_call)
    db_session.commit()

    count = run_purge(db_session)
    assert count == 1

    db_session.refresh(old_call)
    assert old_call.transcript == PURGE_PLACEHOLDER
    assert old_call.summary == PURGE_PLACEHOLDER


def test_purge_never_touches_recent_calls(client, db_session):
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    recent_call = Call(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="inbound", status="completed",
        provider="retell", transcript="Contenu récent", summary="Résumé récent",
        started_at=datetime.utcnow() - timedelta(days=30),
    )
    db_session.add(recent_call)
    db_session.commit()

    run_purge(db_session)

    db_session.refresh(recent_call)
    assert recent_call.transcript == "Contenu récent"


def test_purge_respects_retention_hold(client, db_session):
    """Test central : un appel sous litige (retention_hold) n'est jamais purgé, même après 6 mois."""
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    held_call = Call(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="inbound", status="completed",
        provider="retell", transcript="Contenu sous litige", summary="Résumé sous litige",
        started_at=datetime.utcnow() - timedelta(days=400), retention_hold=True,
    )
    db_session.add(held_call)
    db_session.commit()

    count = run_purge(db_session)
    assert count == 0

    db_session.refresh(held_call)
    assert held_call.transcript == "Contenu sous litige"


def test_purge_is_idempotent_does_not_repurge_already_purged(client, db_session):
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    call = Call(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="inbound", status="completed",
        provider="retell", transcript="À purger", summary="À purger",
        started_at=datetime.utcnow() - timedelta(days=200),
    )
    db_session.add(call)
    db_session.commit()

    first_count = run_purge(db_session)
    second_count = run_purge(db_session)
    assert first_count == 1
    assert second_count == 0  # déjà purgé, ne recompte pas


def test_purge_endpoint_requires_super_admin(client):
    headers = setup_org(client)
    response = client.post("/admin/purge-old-calls", headers=headers)
    assert response.status_code == 403


def test_purge_endpoint_works_for_super_admin(client, db_session):
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    call = Call(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), direction="inbound", status="completed",
        provider="retell", transcript="À purger via endpoint",
        started_at=datetime.utcnow() - timedelta(days=200),
    )
    db_session.add(call)
    db_session.commit()

    admin_headers = get_super_admin_headers(client)
    response = client.post("/admin/purge-old-calls", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["purged_count"] == 1
