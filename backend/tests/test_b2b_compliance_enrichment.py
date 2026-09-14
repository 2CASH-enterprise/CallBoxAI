"""
Tests de l'enrichissement du parcours B2B (section 42/43) : liste
repoussoir, détection d'opposition en direct, journal d'audit, champs
enrichis (entreprise, fonction, source).
"""
import json

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def _setup_agent_with_retell_id(client, db_session, headers, retell_agent_id):
    from app.models.agent import Agent
    import uuid as uuid_module

    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.retell_agent_id = retell_agent_id
    db_session.commit()
    return agent


# ---------- Champs enrichis B2B ----------

def test_create_contact_with_enriched_b2b_fields(client):
    headers = setup_org(client)
    response = client.post(
        "/contacts",
        json={"phone": "+33612980001", "company": "ABC Formation", "job_title": "Directeur", "source": "site web"},
        headers=headers,
    )
    body = response.json()
    assert body["company"] == "ABC Formation"
    assert body["job_title"] == "Directeur"
    assert body["source"] == "site web"


def test_csv_import_recognizes_enriched_columns(client):
    headers = setup_org(client)
    csv_content = "phone,societe,fonction,provenance\n+33612980002,XYZ Academy,Directrice commerciale,fournisseur\n"
    response = client.post(
        "/contacts/import/text", json={"content": csv_content}, headers=headers
    )
    assert response.json()["imported"] == 1

    contacts = client.get("/contacts", headers=headers).json()
    contact = next(c for c in contacts if c["phone"] == "+33612980002")
    assert contact["company"] == "XYZ Academy"
    assert contact["job_title"] == "Directrice commerciale"
    assert contact["source"] == "fournisseur"


# ---------- Mise à jour manuelle ----------

def test_can_manually_mark_contact_do_not_call(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612980003"}, headers=headers).json()

    response = client.patch(f"/contacts/{contact['id']}", json={"do_not_call": True}, headers=headers)
    body = response.json()
    assert body["do_not_call"] is True
    assert body["do_not_call_reason"] is not None


def test_update_contact_requires_valid_status(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612980004"}, headers=headers).json()

    response = client.patch(f"/contacts/{contact['id']}", json={"status": "StatutInvalide"}, headers=headers)
    assert response.status_code == 400


def test_cannot_update_contact_from_another_organization(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612980005"}, headers=headers_a).json()

    response = client.patch(f"/contacts/{contact['id']}", json={"do_not_call": True}, headers=headers_b)
    assert response.status_code == 404


# ---------- Liste repoussoir : bloque le Compliance Check ----------

def test_do_not_call_contact_always_blocked_regardless_of_market(client, db_session):
    """Test central : la liste repoussoir bloque même SANS marché ciblé (contrairement aux autres règles)."""
    from app.core.compliance import check_compliance
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612980006"}, headers=headers).json()
    client.patch(f"/contacts/{contact['id']}", json={"do_not_call": True}, headers=headers)

    class FakeAgent:
        source_template = "prospection_b2b"

    allowed, reason = check_compliance(
        db_session, org_id, None, FakeAgent(), uuid_module.UUID(contact["id"])
    )
    assert allowed is False
    assert "repoussoir" in reason.lower()


def test_contact_not_on_do_not_call_list_is_not_blocked_by_this_rule(client, db_session):
    from app.core.compliance import check_compliance
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612980007"}, headers=headers).json()

    class FakeAgent:
        source_template = "prospection_b2b"

    allowed, reason = check_compliance(
        db_session, org_id, None, FakeAgent(), uuid_module.UUID(contact["id"])
    )
    assert allowed is True


# ---------- Détection d'opposition en direct ----------

def test_register_do_not_call_tool_marks_contact(client, db_session):
    from app.models.contact import Contact
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = _setup_agent_with_retell_id(client, db_session, headers, "retell_dnc_001")
    contact = Contact(organization_id=org_id, phone="+33612980008")
    db_session.add(contact)
    db_session.flush()

    client.post("/webhooks/retell", json={
        "event": "call_started",
        "call": {"call_id": "call_dnc_001", "agent_id": "retell_dnc_001", "direction": "outbound", "from_number": "+33612980008"},
    })
    # Force le lien contact_id sur l'appel (normalement déjà fait lors du déclenchement de l'appel sortant)
    from app.models.call import Call
    call = db_session.query(Call).filter(Call.provider_call_id == "call_dnc_001").first()
    call.contact_id = contact.id
    db_session.commit()

    response = client.post(
        "/webhooks/retell/tools/register-do-not-call",
        json={"name": "register_do_not_call", "call": {"call_id": "call_dnc_001"}, "args": {}},
    )
    assert response.status_code == 200
    assert "noté" in response.json()["result"].lower()

    db_session.refresh(contact)
    assert contact.do_not_call is True
    assert contact.do_not_call_at is not None


def test_register_do_not_call_never_crashes_when_call_not_found(client):
    response = client.post(
        "/webhooks/retell/tools/register-do-not-call",
        json={"name": "register_do_not_call", "call": {"call_id": "call_inexistant"}, "args": {}},
    )
    assert response.status_code == 200


# ---------- Journal d'audit ----------

def test_compliance_check_writes_audit_log_on_allow(client, db_session):
    from app.core.compliance import check_compliance
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612980009"}, headers=headers).json()

    class FakeAgent:
        source_template = "prospection_b2b"

    check_compliance(db_session, org_id, None, FakeAgent(), uuid_module.UUID(contact["id"]))

    logs = client.get(f"/contacts/{contact['id']}/compliance-log", headers=headers).json()
    assert len(logs) == 1
    assert logs[0]["decision"] == "allowed"
    assert logs[0]["legal_basis"] == "intérêt légitime (B2B)"


def test_compliance_check_writes_audit_log_on_block(client, db_session):
    from app.core.compliance import check_compliance
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612980010"}, headers=headers).json()
    client.patch(f"/contacts/{contact['id']}", json={"do_not_call": True}, headers=headers)

    class FakeAgent:
        source_template = "prospection_b2b"

    check_compliance(db_session, org_id, None, FakeAgent(), uuid_module.UUID(contact["id"]))

    logs = client.get(f"/contacts/{contact['id']}/compliance-log", headers=headers).json()
    assert logs[0]["decision"] == "blocked"
    assert "repoussoir" in logs[0]["reason"].lower()


def test_compliance_log_isolated_between_organizations(client, db_session):
    from app.core.compliance import check_compliance
    import uuid as uuid_module

    headers_a = setup_org(client)
    headers_b = setup_org(client)
    org_id_a = uuid_module.UUID(headers_a["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612980011"}, headers=headers_a).json()

    class FakeAgent:
        source_template = "prospection_b2b"

    check_compliance(db_session, org_id_a, None, FakeAgent(), uuid_module.UUID(contact["id"]))

    response = client.get(f"/contacts/{contact['id']}/compliance-log", headers=headers_b)
    assert response.json() == []


# ---------- Import CSV : décompte informatif liste repoussoir ----------

def test_import_reports_already_do_not_call_count(client):
    headers = setup_org(client)
    contact = client.post("/contacts", json={"phone": "+33612980012"}, headers=headers).json()
    client.patch(f"/contacts/{contact['id']}", json={"do_not_call": True}, headers=headers)

    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    campaign = client.post("/campaigns", json={"name": "Campagne test", "agent_id": agent["id"]}, headers=headers).json()

    csv_content = "phone\n+33612980012\n+33612980013\n"
    response = client.post(
        f"/campaigns/{campaign['id']}/import",
        files={"file": ("contacts.csv", csv_content, "text/csv")},
        headers=headers,
    )
    assert response.json()["already_do_not_call"] == 1
