"""
Tests du monitoring des erreurs Super Admin — pilotage réel du produit,
plutôt que de dépendre uniquement des journaux serveur invisibles depuis
le dashboard.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def get_super_admin_headers(client):
    response = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": "superadmin-monitoring@example.com", "password": "TestPassword123", "full_name": "Admin Test"},
    )
    token = response.json()["access_token"]
    return auth_headers(token)


# ---------- log_error : la fonction utilitaire elle-même ----------

def test_log_error_persists_to_database(db_session):
    from app.core.error_log import log_error
    from app.models.error_log import ErrorLog

    log_error(db_session, source="test_source", message="Un message de test")

    errors = db_session.query(ErrorLog).filter(ErrorLog.source == "test_source").all()
    assert len(errors) == 1
    assert errors[0].message == "Un message de test"
    assert errors[0].resolved is False


def test_log_error_captures_traceback_when_exception_given(db_session):
    from app.core.error_log import log_error
    from app.models.error_log import ErrorLog

    try:
        raise ValueError("Erreur de test")
    except ValueError as exc:
        log_error(db_session, source="test_source_2", message="Erreur capturée", exc=exc)

    error = db_session.query(ErrorLog).filter(ErrorLog.source == "test_source_2").first()
    assert error.details is not None
    assert "ValueError" in error.details


def test_log_error_never_crashes_the_caller(db_session):
    """Résilience (section 29) : même avec une session invalide, log_error ne doit jamais lever d'exception."""
    from app.core.error_log import log_error

    class BrokenSession:
        def add(self, *args, **kwargs):
            raise RuntimeError("Session cassée")

        def commit(self):
            pass

        def rollback(self):
            pass

    log_error(BrokenSession(), source="test", message="Ne doit pas planter")  # ne doit lever aucune exception


# ---------- Endpoints Super Admin ----------

def test_list_error_logs_requires_super_admin(client):
    headers = setup_org(client)
    response = client.get("/admin/error-logs", headers=headers)
    assert response.status_code == 403


def test_list_error_logs_returns_recent_first(client, db_session):
    from app.core.error_log import log_error
    import time

    log_error(db_session, source="source_a", message="Premier")
    time.sleep(0.01)
    log_error(db_session, source="source_b", message="Second")

    admin_headers = get_super_admin_headers(client)
    response = client.get("/admin/error-logs", headers=admin_headers)
    errors = response.json()
    assert len(errors) >= 2
    assert errors[0]["message"] == "Second"  # le plus récent en premier


def test_list_error_logs_filters_by_resolved_status(client, db_session):
    from app.core.error_log import log_error

    log_error(db_session, source="source_filter", message="Non résolue")

    admin_headers = get_super_admin_headers(client)
    unresolved = client.get("/admin/error-logs?resolved=false", headers=admin_headers).json()
    assert any(e["message"] == "Non résolue" for e in unresolved)

    resolved = client.get("/admin/error-logs?resolved=true", headers=admin_headers).json()
    assert not any(e["message"] == "Non résolue" for e in resolved)


def test_resolve_error_log(client, db_session):
    from app.core.error_log import log_error
    from app.models.error_log import ErrorLog

    log_error(db_session, source="source_resolve", message="À résoudre")
    error = db_session.query(ErrorLog).filter(ErrorLog.source == "source_resolve").first()

    admin_headers = get_super_admin_headers(client)
    response = client.post(f"/admin/error-logs/{error.id}/resolve", headers=admin_headers)
    body = response.json()
    assert body["resolved"] is True
    assert body["resolved_at"] is not None


def test_resolve_nonexistent_error_returns_404(client):
    import uuid as uuid_module

    admin_headers = get_super_admin_headers(client)
    response = client.post(f"/admin/error-logs/{uuid_module.uuid4()}/resolve", headers=admin_headers)
    assert response.status_code == 404


# ---------- Instrumentation réelle : PMS ----------

def test_pms_availability_check_logs_error_on_unexpected_exception(client, db_session):
    """Test d'intégration : une erreur inattendue dans la vérification de disponibilité est bien capturée."""
    from unittest.mock import patch
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = headers["x-organization-id"]

    with patch("app.api.routes.pms.pms_provider") as mock_provider:
        mock_provider.check_availability.side_effect = RuntimeError("Panne simulée du PMS")
        response = client.post(
            f"/pms/tools/availability?organization_id={org_id}",
            json={"check_in": "2026-10-01", "check_out": "2026-10-03"},
        )

    assert response.status_code == 200  # jamais d'erreur exposée à l'agent en direct
    assert response.json()["available"] is False

    from app.models.error_log import ErrorLog
    errors = db_session.query(ErrorLog).filter(ErrorLog.source == "pms_availability_check").all()
    assert len(errors) >= 1
