"""
Tests du Compliance Check (section 42/43 du cahier des charges) — verrou
technique avant tout appel sortant, selon le marché ciblé par la campagne.
"""
from datetime import datetime

from app.core.compliance import check_compliance
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


class FakeAgent:
    def __init__(self, source_template):
        self.source_template = source_template


# ---------- Marché non renseigné : jamais de blocage ----------

def test_no_target_market_never_blocks(client, db_session):
    import uuid as uuid_module

    allowed, reason = check_compliance(
        db_session, uuid_module.uuid4(), None, FakeAgent("prospection_b2c"), uuid_module.uuid4()
    )
    assert allowed is True
    assert reason is None


def test_unknown_market_never_blocks(client, db_session):
    """Résilience (section 29) : un marché non modélisé ne doit jamais bloquer par défaut."""
    import uuid as uuid_module

    allowed, reason = check_compliance(
        db_session, uuid_module.uuid4(), "mars", FakeAgent("prospection_b2c"), uuid_module.uuid4()
    )
    assert allowed is True


# ---------- France : consentement B2C obligatoire ----------

def test_france_b2c_without_consent_is_blocked(client, db_session):
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612950001"}, headers=headers).json()

    # Un mardi 14h, dans les horaires légaux — seul le consentement doit bloquer
    now = datetime(2026, 9, 8, 14, 0)  # mardi
    allowed, reason = check_compliance(
        db_session, org_id, "france", FakeAgent("prospection_b2c"), uuid_module.UUID(contact["id"]), now
    )
    assert allowed is False
    assert "consentement" in reason.lower()


def test_france_b2c_with_valid_consent_is_allowed(client, db_session):
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    client.post(
        "/consent",
        json={"contact_phone": "+33612950002", "source": "facebook_lead_ads", "consent_text": "Test"},
        headers=headers,
    )
    contact_id = uuid_module.UUID(client.get("/contacts", headers=headers).json()[0]["id"])

    now = datetime(2026, 9, 8, 14, 0)  # mardi, dans les horaires
    allowed, reason = check_compliance(
        db_session, org_id, "france", FakeAgent("prospection_b2c"), contact_id, now
    )
    assert allowed is True
    assert reason is None


def test_france_b2b_never_requires_consent(client, db_session):
    """Test central : le B2B reste sous intérêt légitime, jamais de blocage sur le consentement."""
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612950003"}, headers=headers).json()

    now = datetime(2026, 9, 8, 14, 0)  # mardi, dans les horaires
    allowed, reason = check_compliance(
        db_session, org_id, "france", FakeAgent("prospection_b2b"), uuid_module.UUID(contact["id"]), now
    )
    assert allowed is True


def test_france_fidelisation_templates_treated_as_b2c(client, db_session):
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612950004"}, headers=headers).json()

    now = datetime(2026, 9, 8, 14, 0)
    for template in ["reactivation", "upsell", "cross_sell"]:
        allowed, reason = check_compliance(
            db_session, org_id, "france", FakeAgent(template), uuid_module.UUID(contact["id"]), now
        )
        assert allowed is False, f"{template} devrait être traité comme B2C"


# ---------- France : horaires légaux ----------

def test_france_blocks_outside_legal_hours(client, db_session):
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612950005"}, headers=headers).json()

    # Mardi 22h — hors des horaires légaux (10h-20h)
    now = datetime(2026, 9, 8, 22, 0)
    allowed, reason = check_compliance(
        db_session, org_id, "france", FakeAgent("prospection_b2b"), uuid_module.UUID(contact["id"]), now
    )
    assert allowed is False
    assert "horaires" in reason.lower()


def test_france_blocks_on_weekend(client, db_session):
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612950006"}, headers=headers).json()

    # Samedi 14h — hors des jours autorisés (lundi-vendredi), même en B2B
    now = datetime(2026, 9, 12, 14, 0)  # samedi
    allowed, reason = check_compliance(
        db_session, org_id, "france", FakeAgent("prospection_b2b"), uuid_module.UUID(contact["id"]), now
    )
    assert allowed is False


# ---------- Côte d'Ivoire : profil permissif tant que non précisé ----------

def test_cote_ivoire_does_not_require_consent(client, db_session):
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+2250700000001"}, headers=headers).json()

    allowed, reason = check_compliance(
        db_session, org_id, "cote_ivoire", FakeAgent("prospection_b2b"), uuid_module.UUID(contact["id"])
    )
    assert allowed is True


# ---------- Intégration : lot de campagne respecte le verrou ----------

def test_campaign_batch_skips_blocked_contact_without_calling(client, db_session):
    """Test d'intégration : un contact bloqué n'est ni appelé, ni compté comme échec."""
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent B2C France", "category": "prospection"}, headers=headers).json()

    # Force le source_template B2C directement en base pour le test (le
    # champ n'est normalement peuplé qu'au traitement d'une demande d'agent)
    from app.models.agent import Agent
    import uuid as uuid_module

    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.source_template = "prospection_b2c"
    db_session.commit()

    campaign = client.post(
        "/campaigns",
        json={"name": "Campagne France sans consentement", "agent_id": agent["id"], "target_market": "france", "schedule_start": "00:00", "schedule_end": "23:59"},
        headers=headers,
    ).json()

    csv_content = "phone\n+33612950099\n"
    client.post(
        f"/campaigns/{campaign['id']}/import",
        files={"file": ("contacts.csv", csv_content, "text/csv")},
        headers=headers,
    )
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)

    result = client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers).json()
    assert result["blocked_compliance"] == 1
    assert result["completed"] == 0
    assert result["failed"] == 0
