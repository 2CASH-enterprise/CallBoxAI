"""
Tests de la base de connaissances / RAG (section 10 du cahier des charges).
"""
import io

from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def test_create_text_document_creates_chunks(client):
    headers = setup_org(client)
    response = client.post(
        "/knowledge/documents",
        json={"title": "FAQ", "content": "Nos bureaux sont ouverts du lundi au vendredi, de 8h à 18h."},
        headers=headers,
    )
    assert response.status_code == 200
    doc = response.json()
    assert doc["chunks_count"] >= 1
    assert doc["source_type"] == "text"


def test_create_document_rejects_empty_content(client):
    headers = setup_org(client)
    response = client.post("/knowledge/documents", json={"title": "Vide", "content": "   "}, headers=headers)
    assert response.status_code == 400


def test_upload_txt_file_creates_document(client):
    headers = setup_org(client)
    files = {"file": ("tarifs.txt", io.BytesIO("Nos tarifs commencent à 10000 FCFA par mois.".encode()), "text/plain")}
    response = client.post("/knowledge/documents/upload", headers=headers, files=files)
    assert response.status_code == 200
    assert response.json()["source_type"] == "txt_upload"


def test_upload_rejects_non_txt_file(client):
    headers = setup_org(client)
    files = {"file": ("document.pdf", io.BytesIO(b"contenu binaire"), "application/pdf")}
    response = client.post("/knowledge/documents/upload", headers=headers, files=files)
    assert response.status_code == 400


def test_list_and_delete_document(client):
    headers = setup_org(client)
    doc = client.post(
        "/knowledge/documents", json={"title": "Doc", "content": "Contenu de test pour la suppression."}, headers=headers
    ).json()

    docs = client.get("/knowledge/documents", headers=headers).json()
    assert len(docs) == 1

    delete_response = client.delete(f"/knowledge/documents/{doc['id']}", headers=headers)
    assert delete_response.status_code == 204

    docs_after = client.get("/knowledge/documents", headers=headers).json()
    assert len(docs_after) == 0


def test_search_ranks_relevant_document_first(client):
    """
    Test central du RAG : une recherche sur les horaires doit remonter le
    document qui parle des horaires, pas celui qui parle des tarifs.
    """
    headers = setup_org(client)
    client.post(
        "/knowledge/documents",
        json={"title": "Tarifs", "content": "Nos tarifs commencent à 10000 FCFA par mois pour l'offre de base."},
        headers=headers,
    )
    client.post(
        "/knowledge/documents",
        json={"title": "Horaires", "content": "Nos horaires d'ouverture sont du lundi au vendredi, de 8h à 18h."},
        headers=headers,
    )

    response = client.post("/knowledge/search", json={"query": "quels sont vos horaires d'ouverture", "top_k": 2}, headers=headers)
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert results[0]["document_title"] == "Horaires"


def test_knowledge_isolated_between_organizations(client):
    headers_a = setup_org(client)
    headers_b = setup_org(client)

    client.post("/knowledge/documents", json={"title": "Doc A", "content": "Contenu réservé à l'entreprise A."}, headers=headers_a)

    docs_b = client.get("/knowledge/documents", headers=headers_b).json()
    assert len(docs_b) == 0

    search_b = client.post("/knowledge/search", json={"query": "contenu réservé", "top_k": 3}, headers=headers_b).json()
    assert len(search_b) == 0


def test_call_pipeline_consults_knowledge_base(client):
    """
    Critère d'acceptation MVP (section 32) : "l'agent peut consulter sa base
    de connaissances". Vérifie que le pipeline d'appel l'utilise réellement.
    """
    headers = setup_org(client)
    client.post(
        "/knowledge/documents",
        json={"title": "Info", "content": "Qualification de prospects et prise de rendez-vous pour l'équipe commerciale."},
        headers=headers,
    )

    agent = client.post(
        "/agents",
        json={"name": "Agent commercial", "objective": "Qualification de prospects et prise de rendez-vous"},
        headers=headers,
    ).json()

    response = client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers,
    )
    assert response.status_code == 200
    call = response.json()
    assert call["knowledge_context"] is not None
    assert "Base de connaissances consultée" in call["transcript"]


def test_call_pipeline_works_without_knowledge_base(client):
    """Sans aucun document, le pipeline d'appel doit fonctionner normalement (pas d'erreur)."""
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent sans KB"}, headers=headers).json()

    response = client.post(
        "/calls",
        json={"agent_id": agent["id"], "to_number": "+221770000000", "from_number": "+221780000000"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["knowledge_context"] is None
