"""
Tests de la synchronisation de la base de connaissances Retell (section
42 du cahier des charges) — brancher réellement le RAG sur l'appel en
direct, plutôt que sur une recherche manuelle uniquement.
"""
from unittest.mock import patch

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


@patch("app.providers.voice.retell_provider.RetellProvider.create_knowledge_base")
def test_first_document_creates_retell_knowledge_base(mock_create_kb, client, db_session):
    mock_create_kb.return_value = {"knowledge_base_id": "kb_fake_001"}
    headers = setup_org(client)

    with patch("app.core.knowledge_sync.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        client.post("/knowledge/documents", json={"title": "Horaires", "content": "Ouvert de 9h à 18h."}, headers=headers)

    mock_create_kb.assert_called_once()
    _, kwargs = mock_create_kb.call_args
    assert kwargs["texts"][0]["title"] == "Horaires"

    from app.models.organization import Organization
    import uuid as uuid_module

    org = db_session.query(Organization).filter(Organization.id == uuid_module.UUID(headers["x-organization-id"])).first()
    assert org.retell_knowledge_base_id == "kb_fake_001"


@patch("app.providers.voice.retell_provider.RetellProvider.add_knowledge_base_sources")
@patch("app.providers.voice.retell_provider.RetellProvider.create_knowledge_base")
def test_second_document_adds_source_not_recreate(mock_create_kb, mock_add_sources, client):
    """Test central : le deuxième document ne doit JAMAIS recréer la base, juste y ajouter une source."""
    mock_create_kb.return_value = {"knowledge_base_id": "kb_fake_002"}
    headers = setup_org(client)

    with patch("app.core.knowledge_sync.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        client.post("/knowledge/documents", json={"title": "Doc 1", "content": "Contenu 1"}, headers=headers)
        client.post("/knowledge/documents", json={"title": "Doc 2", "content": "Contenu 2"}, headers=headers)

    mock_create_kb.assert_called_once()
    mock_add_sources.assert_called_once()
    args, kwargs = mock_add_sources.call_args
    assert args[0] == "kb_fake_002"


def test_knowledge_sync_failure_never_blocks_document_creation(client):
    """Résilience (section 29) : un échec Retell ne doit jamais empêcher la création locale du document."""
    headers = setup_org(client)

    with patch("app.core.knowledge_sync.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        with patch("app.providers.voice.retell_provider.RetellProvider.create_knowledge_base", side_effect=Exception("Retell indisponible")):
            response = client.post("/knowledge/documents", json={"title": "Doc", "content": "Contenu"}, headers=headers)

    assert response.status_code == 200
    documents = client.get("/knowledge/documents", headers=headers).json()
    assert len(documents) == 1


def test_knowledge_sync_skipped_gracefully_without_retell_configured(client):
    """Sans Retell configuré, la synchronisation est simplement ignorée, pas d'erreur."""
    headers = setup_org(client)
    response = client.post("/knowledge/documents", json={"title": "Doc", "content": "Contenu"}, headers=headers)
    assert response.status_code == 200


# ---------- Site web / réseaux sociaux ----------

def test_get_organization_sources_defaults_empty(client):
    headers = setup_org(client)
    sources = client.get("/knowledge/sources", headers=headers).json()
    assert sources["website_url"] is None
    assert sources["social_media_urls"] is None
    assert sources["documents_count"] == 0


@patch("app.providers.voice.retell_provider.RetellProvider.create_knowledge_base")
def test_update_website_url_syncs_to_retell(mock_create_kb, client):
    mock_create_kb.return_value = {"knowledge_base_id": "kb_fake_003"}
    headers = setup_org(client)

    with patch("app.core.knowledge_sync.settings") as mock_settings:
        mock_settings.voice_provider = "retell"
        mock_settings.retell_api_key = "fake_key"
        response = client.patch("/knowledge/sources", json={"website_url": "https://exemple-hotel.com"}, headers=headers)

    assert response.json()["website_url"] == "https://exemple-hotel.com"
    mock_create_kb.assert_called_once()
    _, kwargs = mock_create_kb.call_args
    assert kwargs["urls"] == ["https://exemple-hotel.com"]


def test_update_social_media_urls_multiline(client):
    headers = setup_org(client)
    response = client.patch(
        "/knowledge/sources",
        json={"social_media_urls": "https://facebook.com/exemple\nhttps://instagram.com/exemple"},
        headers=headers,
    )
    assert "facebook.com" in response.json()["social_media_urls"]


def test_documents_count_increases_with_each_document(client):
    headers = setup_org(client)
    client.post("/knowledge/documents", json={"title": "Doc 1", "content": "Contenu 1"}, headers=headers)
    client.post("/knowledge/documents", json={"title": "Doc 2", "content": "Contenu 2"}, headers=headers)

    sources = client.get("/knowledge/sources", headers=headers).json()
    assert sources["documents_count"] == 2


def test_sources_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)
    client.patch("/knowledge/sources", json={"website_url": "https://a.com"}, headers=headers_a)

    sources_b = client.get("/knowledge/sources", headers=headers_b).json()
    assert sources_b["website_url"] is None


# ---------- Provisionnement avec base de connaissances ----------

def test_agent_provisioning_includes_knowledge_base_id_when_set(client, db_session):
    from app.models.organization import Organization
    import uuid as uuid_module

    headers = setup_org(client)
    org = db_session.query(Organization).filter(Organization.id == uuid_module.UUID(headers["x-organization-id"])).first()
    org.retell_knowledge_base_id = "kb_existing_001"
    db_session.commit()

    with patch("app.providers.voice.retell_provider.RetellProvider.create_llm") as mock_create_llm, \
         patch("app.providers.voice.retell_provider.RetellProvider.create_retell_agent") as mock_create_agent, \
         patch("app.providers.voice.retell_provider.RetellProvider.publish_agent"):
        mock_create_llm.return_value = {"llm_id": "llm_fake"}
        mock_create_agent.return_value = {"agent_id": "agent_fake"}

        with patch("app.api.routes.agents.settings") as mock_settings:
            mock_settings.voice_provider = "retell"
            mock_settings.retell_api_key = "fake_key"
            mock_settings.retell_default_llm_model = "gpt-4o-mini"
            mock_settings.retell_default_voice_id = "cartesia-Emma"
            mock_settings.public_base_url = ""

            client.post("/agents", json={"name": "Agent test"}, headers=headers)

        _, kwargs = mock_create_llm.call_args
        assert kwargs["knowledge_base_id"] == "kb_existing_001"
