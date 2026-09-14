"""
Tests de la certification de consentement à l'import (section 42/43) —
nécessaire pour les campagnes de Fidélisation, dont les contacts arrivent
par CSV (clients existants), pas via un formulaire comme Facebook Lead Ads
qui capture le consentement automatiquement.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


# ---------- Import direct CRM (fichier) ----------

def test_import_without_certify_creates_no_consent(client):
    headers = setup_org(client)
    csv_content = "phone\n+33612990001\n"
    response = client.post(
        "/contacts/import/upload",
        files={"file": ("contacts.csv", csv_content, "text/csv")},
        data={"certify_consent": "false"},
        headers=headers,
    )
    assert response.json()["consent_certified_count"] == 0

    from app.core.compliance import check_compliance
    contacts = client.get("/contacts", headers=headers).json()
    assert contacts[0]["phone"] == "+33612990001"


def test_import_with_certify_creates_consent_record_per_contact(client):
    headers = setup_org(client)
    csv_content = "phone\n+33612990002\n+33612990003\n"
    response = client.post(
        "/contacts/import/upload",
        files={"file": ("contacts.csv", csv_content, "text/csv")},
        data={"certify_consent": "true", "consent_note": "Clients ayant souscrit avant 2025"},
        headers=headers,
    )
    assert response.json()["consent_certified_count"] == 2

    contacts = client.get("/contacts", headers=headers).json()
    contact = next(c for c in contacts if c["phone"] == "+33612990002")
    logs = client.get(f"/consent?contact_id={contact['id']}", headers=headers).json()
    assert len(logs) == 1
    assert logs[0]["source"] == "import_certifie_client"
    assert "DÉCLARÉ" in logs[0]["consent_text"]
    assert "Clients ayant souscrit avant 2025" in logs[0]["consent_text"]


def test_certified_consent_unblocks_fidelisation_campaign_in_france(client, db_session):
    """Test central : sans certification, bloqué en France ; avec, autorisé."""
    from app.core.compliance import check_compliance
    from app.models.agent import Agent
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    agent = client.post("/agents", json={"name": "Agent Réactivation"}, headers=headers).json()
    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.source_template = "reactivation"
    db_session.commit()

    # Sans certification : bloqué
    csv_content = "phone\n+33612990004\n"
    client.post(
        "/contacts/import/upload",
        files={"file": ("contacts.csv", csv_content, "text/csv")},
        data={"certify_consent": "false"},
        headers=headers,
    )
    contact = client.get("/contacts", headers=headers).json()[0]
    from datetime import datetime
    allowed, reason = check_compliance(
        db_session, org_id, "france", db_agent, uuid_module.UUID(contact["id"]), datetime(2026, 9, 8, 14, 0),
    )
    assert allowed is False

    # Avec certification (nouveau contact) : autorisé
    csv_content2 = "phone\n+33612990005\n"
    client.post(
        "/contacts/import/upload",
        files={"file": ("contacts.csv", csv_content2, "text/csv")},
        data={"certify_consent": "true"},
        headers=headers,
    )
    contacts = client.get("/contacts", headers=headers).json()
    contact2 = next(c for c in contacts if c["phone"] == "+33612990005")
    allowed2, reason2 = check_compliance(
        db_session, org_id, "france", db_agent, uuid_module.UUID(contact2["id"]), datetime(2026, 9, 8, 14, 0),
    )
    assert allowed2 is True


# ---------- Import texte collé ----------

def test_import_text_with_certify_consent(client):
    headers = setup_org(client)
    response = client.post(
        "/contacts/import/text",
        json={"content": "phone\n+33612990006\n", "certify_consent": True, "consent_note": "Import test"},
        headers=headers,
    )
    assert response.json()["consent_certified_count"] == 1


# ---------- Import campagne ----------

def test_campaign_import_with_certify_consent(client):
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    campaign = client.post("/campaigns", json={"name": "Campagne Fidélisation", "agent_id": agent["id"]}, headers=headers).json()

    csv_content = "phone\n+33612990007\n"
    response = client.post(
        f"/campaigns/{campaign['id']}/import",
        files={"file": ("contacts.csv", csv_content, "text/csv")},
        data={"certify_consent": "true", "consent_note": "Base clients CRM"},
        headers=headers,
    )
    assert response.json()["consent_certified_count"] == 1

    contacts = client.get("/contacts", headers=headers).json()
    logs = client.get(f"/consent?contact_id={contacts[0]['id']}", headers=headers).json()
    assert "Base clients CRM" in logs[0]["consent_text"]


def test_campaign_import_without_certify_defaults_to_false(client):
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()
    campaign = client.post("/campaigns", json={"name": "Campagne test", "agent_id": agent["id"]}, headers=headers).json()

    csv_content = "phone\n+33612990008\n"
    response = client.post(
        f"/campaigns/{campaign['id']}/import",
        files={"file": ("contacts.csv", csv_content, "text/csv")},
        headers=headers,
    )
    assert response.json()["consent_certified_count"] == 0
