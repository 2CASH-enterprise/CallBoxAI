"""
Tests des droits RGPD génériques (section 42/43) — accès et effacement,
applicables à toute la plateforme, quel que soit l'agent à l'origine du
contact.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


# ---------- Enregistrement d'une demande ----------

def test_create_access_request(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613000001"}, headers=headers).json()

    response = client.post(
        f"/contacts/{contact['id']}/data-subject-requests",
        json={"request_type": "access", "notes": "Demande reçue par email"},
        headers=headers,
    )
    body = response.json()
    assert body["request_type"] == "access"
    assert body["status"] == "pending"


def test_create_request_rejects_invalid_type(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613000002"}, headers=headers).json()

    response = client.post(
        f"/contacts/{contact['id']}/data-subject-requests",
        json={"request_type": "n_importe_quoi"},
        headers=headers,
    )
    assert response.status_code == 400


# ---------- Export (droit d'accès) ----------

def test_data_export_includes_contact_and_calls(client, db_session):
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33613000003", "first_name": "Awa"}, headers=headers).json()
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    db_session.add(Call(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), contact_id=uuid_module.UUID(contact["id"]),
        direction="inbound", status="completed", provider="retell", transcript="Bonjour, je voudrais des informations.",
    ))
    db_session.commit()

    export = client.get(f"/contacts/{contact['id']}/data-export", headers=headers).json()
    assert export["contact"]["first_name"] == "Awa"
    assert len(export["calls"]) == 1
    assert export["calls"][0]["transcript"] == "Bonjour, je voudrais des informations."


def test_data_export_fulfills_pending_access_request(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613000004"}, headers=headers).json()
    client.post(f"/contacts/{contact['id']}/data-subject-requests", json={"request_type": "access"}, headers=headers)

    client.get(f"/contacts/{contact['id']}/data-export", headers=headers)

    requests = client.get(f"/contacts/{contact['id']}/data-subject-requests", headers=headers).json()
    assert requests[0]["status"] == "fulfilled"
    assert requests[0]["fulfilled_at"] is not None


def test_data_export_includes_whatsapp_matched_by_phone(client, db_session):
    from app.models.whatsapp_log import WhatsAppLog
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33613000005"}, headers=headers).json()
    db_session.add(WhatsAppLog(organization_id=org_id, to_number="+33613000005", body="Voici notre offre"))
    db_session.commit()

    export = client.get(f"/contacts/{contact['id']}/data-export", headers=headers).json()
    assert len(export["whatsapp_messages"]) == 1
    assert export["whatsapp_messages"][0]["body"] == "Voici notre offre"


# ---------- Effacement (droit à l'oubli) ----------

def test_erase_anonymizes_identity_fields(client):
    headers = setup_org(client)
    contact = client.post(
        "/contacts", json={"phone": "+33613000006", "first_name": "Jean", "email": "jean@example.com", "company": "ABC"},
        headers=headers,
    ).json()

    response = client.post(f"/contacts/{contact['id']}/erase", headers=headers)
    assert response.status_code == 200

    updated = client.get("/contacts", headers=headers).json()
    erased = next(c for c in updated if c["id"] == contact["id"])
    assert erased["first_name"] is None
    assert erased["email"] is None
    assert erased["company"] is None
    assert erased["phone"] == "+33613000006"  # le numéro reste, mais...


def test_erase_permanently_sets_do_not_call(client, db_session):
    """Test central : le numéro reste en liste repoussoir définitive après effacement."""
    from app.core.compliance import check_compliance
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33613000007"}, headers=headers).json()

    client.post(f"/contacts/{contact['id']}/erase", headers=headers)

    class FakeAgent:
        source_template = "prospection_b2c"

    allowed, reason = check_compliance(db_session, org_id, None, FakeAgent(), uuid_module.UUID(contact["id"]))
    assert allowed is False
    assert "repoussoir" in reason.lower()


def test_erase_redacts_call_transcripts(client, db_session):
    from app.models.call import Call
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33613000008"}, headers=headers).json()
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    call = Call(
        organization_id=org_id, agent_id=uuid_module.UUID(agent["id"]), contact_id=uuid_module.UUID(contact["id"]),
        direction="inbound", status="completed", provider="retell", transcript="Contenu sensible à effacer",
    )
    db_session.add(call)
    db_session.commit()

    response = client.post(f"/contacts/{contact['id']}/erase", headers=headers)
    assert response.json()["calls_redacted"] == 1

    db_session.refresh(call)
    assert "Effacé" in call.transcript
    assert "Contenu sensible" not in call.transcript


def test_erase_fulfills_pending_erasure_request(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613000009"}, headers=headers).json()
    client.post(f"/contacts/{contact['id']}/data-subject-requests", json={"request_type": "erasure"}, headers=headers)

    client.post(f"/contacts/{contact['id']}/erase", headers=headers)

    requests = client.get(f"/contacts/{contact['id']}/data-subject-requests", headers=headers).json()
    erasure_request = next(r for r in requests if r["request_type"] == "erasure")
    assert erasure_request["status"] == "fulfilled"


def test_erase_without_prior_request_still_creates_audit_trail(client):
    """Une effacement déclenché directement (sans demande enregistrée avant) laisse quand même une trace."""
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613000010"}, headers=headers).json()

    client.post(f"/contacts/{contact['id']}/erase", headers=headers)

    requests = client.get(f"/contacts/{contact['id']}/data-subject-requests", headers=headers).json()
    assert len(requests) == 1
    assert requests[0]["request_type"] == "erasure"
    assert requests[0]["status"] == "fulfilled"


def test_data_subject_endpoints_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33613000011"}, headers=headers_a).json()

    response = client.get(f"/contacts/{contact['id']}/data-export", headers=headers_b)
    assert response.status_code == 404

    response2 = client.post(f"/contacts/{contact['id']}/erase", headers=headers_b)
    assert response2.status_code == 404
