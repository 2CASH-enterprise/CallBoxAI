"""
Tests du registre de consentement (section 42/43 du cahier des charges) —
preuve horodatée et immuable, nécessaire à la prospection B2C conforme.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_record_consent_creates_contact_and_ledger_entry(client):
    headers = setup_org(client)
    response = client.post(
        "/consent",
        json={
            "contact_phone": "+33612900001",
            "contact_name": "Awa",
            "source": "facebook_lead_ads",
            "campaign_reference": "campagne-rentree-2026",
            "consent_text": "J'accepte d'être contacté par téléphone au sujet de cette offre.",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "facebook_lead_ads"
    assert body["revoked_at"] is None

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1
    assert contacts[0]["phone"] == "+33612900001"


def test_record_consent_reuses_existing_contact(client):
    headers = setup_org(client)
    client.post("/contacts", json={"phone": "+33612900002", "first_name": "Déjà là"}, headers=headers)

    client.post(
        "/consent",
        json={"contact_phone": "+33612900002", "source": "formulaire_web", "consent_text": "Test"},
        headers=headers,
    )

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1


def test_consent_never_overwrites_previous_record(client):
    """Test central : chaque consentement crée une NOUVELLE ligne, l'historique reste intact."""
    headers = setup_org(client)
    client.post(
        "/consent",
        json={"contact_phone": "+33612900003", "source": "facebook_lead_ads", "consent_text": "Première campagne"},
        headers=headers,
    )
    client.post(
        "/consent",
        json={"contact_phone": "+33612900003", "source": "facebook_lead_ads", "consent_text": "Deuxième campagne"},
        headers=headers,
    )

    contact_id = client.get("/contacts", headers=headers).json()[0]["id"]
    history = client.get(f"/consent?contact_id={contact_id}", headers=headers).json()
    assert len(history) == 2
    texts = {r["consent_text"] for r in history}
    assert texts == {"Première campagne", "Deuxième campagne"}


def test_revoke_consent_sets_revoked_at_without_altering_original_facts(client):
    headers = setup_org(client)
    record = client.post(
        "/consent",
        json={"contact_phone": "+33612900004", "source": "facebook_lead_ads", "consent_text": "Texte original"},
        headers=headers,
    ).json()

    revoked = client.post(f"/consent/{record['id']}/revoke", headers=headers).json()
    assert revoked["revoked_at"] is not None
    assert revoked["consent_text"] == "Texte original"  # jamais réécrit
    assert revoked["source"] == "facebook_lead_ads"  # jamais réécrit


def test_revoking_already_revoked_consent_is_idempotent(client):
    headers = setup_org(client)
    record = client.post(
        "/consent",
        json={"contact_phone": "+33612900005", "source": "test", "consent_text": "Test"},
        headers=headers,
    ).json()

    first = client.post(f"/consent/{record['id']}/revoke", headers=headers).json()
    second = client.post(f"/consent/{record['id']}/revoke", headers=headers).json()
    assert first["revoked_at"] == second["revoked_at"]  # pas réécrit à un second appel


def test_consent_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    client.post(
        "/consent",
        json={"contact_phone": "+33612900006", "source": "test", "consent_text": "Confidentiel A"},
        headers=headers_a,
    )

    all_b = client.get("/consent", headers=headers_b).json()
    assert len(all_b) == 0


def test_cannot_revoke_consent_from_another_organization(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    record = client.post(
        "/consent",
        json={"contact_phone": "+33612900007", "source": "test", "consent_text": "Test"},
        headers=headers_a,
    ).json()

    response = client.post(f"/consent/{record['id']}/revoke", headers=headers_b)
    assert response.status_code == 404


# ---------- Fonction has_valid_consent (utilisée par le futur Compliance Check) ----------

def test_has_valid_consent_true_after_recording(client, db_session):
    from app.api.routes.consent import has_valid_consent
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    client.post(
        "/consent",
        json={"contact_phone": "+33612900008", "source": "test", "consent_text": "Test"},
        headers=headers,
    )
    contact_id = uuid_module.UUID(client.get("/contacts", headers=headers).json()[0]["id"])

    assert has_valid_consent(db_session, org_id, contact_id) is True


def test_has_valid_consent_false_after_revocation(client, db_session):
    from app.api.routes.consent import has_valid_consent
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    record = client.post(
        "/consent",
        json={"contact_phone": "+33612900009", "source": "test", "consent_text": "Test"},
        headers=headers,
    ).json()
    contact_id = uuid_module.UUID(client.get("/contacts", headers=headers).json()[0]["id"])

    client.post(f"/consent/{record['id']}/revoke", headers=headers)

    assert has_valid_consent(db_session, org_id, contact_id) is False


def test_has_valid_consent_false_when_never_recorded(client, db_session):
    from app.api.routes.consent import has_valid_consent
    import uuid as uuid_module

    headers = setup_org(client)
    org_id = uuid_module.UUID(headers["x-organization-id"])
    contact = client.post("/contacts", json={"phone": "+33612900010"}, headers=headers).json()

    assert has_valid_consent(db_session, org_id, uuid_module.UUID(contact["id"])) is False
