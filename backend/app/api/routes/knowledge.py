"""
Endpoints Base de connaissances (section 10 du cahier des charges).
"""
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.chunking import chunk_text
from app.core.rag import retrieve_top_chunks
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.models.organization import Organization
from app.providers.embeddings.mock import MockEmbeddingProvider
from app.core.knowledge_sync import sync_knowledge_source

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

embedding_provider = MockEmbeddingProvider()


# ---------- Schémas ----------

class DocumentCreate(BaseModel):
    title: str
    content: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    source_type: str
    chunks_count: int
    created_at: datetime


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


class SearchResultOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    score: float


# ---------- Aides ----------

def _index_document(db: Session, organization_id: uuid.UUID, title: str, content: str, source_type: str) -> KnowledgeDocument:
    document = KnowledgeDocument(organization_id=organization_id, title=title, source_type=source_type)
    db.add(document)
    db.flush()

    for i, chunk_content in enumerate(chunk_text(content)):
        vector = embedding_provider.embed(chunk_content)
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                organization_id=organization_id,
                chunk_index=i,
                content=chunk_content,
                embedding=json.dumps(vector),
            )
        )

    db.commit()
    db.refresh(document)

    # Synchronise vers la base de connaissances Retell (section 42) — c'est
    # ce qui rend le document réellement consultable par l'agent PENDANT
    # l'appel, en plus de notre propre index local (utilisé par /search).
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if organization:
        sync_knowledge_source(db, organization, texts=[{"title": title, "text": content}])

    return document


def _to_document_out(db: Session, document: KnowledgeDocument) -> DocumentOut:
    count = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).count()
    return DocumentOut(
        id=document.id,
        organization_id=document.organization_id,
        title=document.title,
        source_type=document.source_type,
        chunks_count=count,
        created_at=document.created_at,
    )


# ---------- Endpoints ----------

@router.post("/documents", response_model=DocumentOut)
def create_text_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """Ajout d'un document via texte collé directement (FAQ, tarifs, horaires...)."""
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="Le contenu du document est vide")
    document = _index_document(db, organization_id, payload.title, payload.content, source_type="text")
    return _to_document_out(db, document)


@router.post("/documents/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Upload d'un fichier texte (.txt). L'extraction PDF/DOCX (section 10) est
    prévue dans une prochaine itération — pour l'instant, convertir le
    document en texte brut avant import, ou utiliser /documents (texte collé).
    """
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers .txt sont supportés pour l'instant")

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Le fichier est vide")

    document = _index_document(db, organization_id, file.filename, raw, source_type="txt_upload")
    return _to_document_out(db, document)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    documents = db.query(KnowledgeDocument).filter(KnowledgeDocument.organization_id == organization_id).all()
    return [_to_document_out(db, d) for d in documents]


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    document = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id, KnowledgeDocument.organization_id == organization_id
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable pour cette organisation")

    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document_id).delete()
    db.delete(document)
    db.commit()


@router.post("/search", response_model=list[SearchResultOut])
def search_knowledge_base(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Recherche par similarité dans la base de connaissances de l'organisation
    — démonstration/test manuel du pipeline RAG maison. L'appel en direct,
    lui, s'appuie sur la base de connaissances NATIVE de Retell (section 42),
    synchronisée à chaque ajout de document/source — voir app.core.knowledge_sync.
    """
    results = retrieve_top_chunks(db, organization_id, payload.query, embedding_provider, top_k=payload.top_k)
    return [SearchResultOut(**r) for r in results]


# ---------- Sources d'entreprise : site web, réseaux sociaux (section 42) ----------

class OrganizationSourcesOut(BaseModel):
    website_url: str | None
    social_media_urls: str | None
    documents_count: int
    facebook_page_id: str | None
    facebook_page_access_token: str | None


class OrganizationSourcesUpdate(BaseModel):
    website_url: str | None = None
    social_media_urls: str | None = None  # une URL par ligne
    facebook_page_id: str | None = None
    facebook_page_access_token: str | None = None


@router.get("/sources", response_model=OrganizationSourcesOut)
def get_organization_sources(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    documents_count = db.query(KnowledgeDocument).filter(KnowledgeDocument.organization_id == organization_id).count()
    return OrganizationSourcesOut(
        website_url=organization.website_url if organization else None,
        social_media_urls=organization.social_media_urls if organization else None,
        documents_count=documents_count,
        facebook_page_id=organization.facebook_page_id if organization else None,
        facebook_page_access_token=organization.facebook_page_access_token if organization else None,
    )


@router.patch("/sources", response_model=OrganizationSourcesOut)
def update_organization_sources(
    payload: OrganizationSourcesUpdate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    """
    Enregistre le site web et/ou les réseaux sociaux de l'entreprise
    (recommandé, jamais obligatoire) — transmis à Retell pour un crawl
    automatique et une resynchronisation toutes les 24h (section 42).
    """
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organisation introuvable")

    new_urls = []
    if payload.website_url is not None and payload.website_url != organization.website_url:
        organization.website_url = payload.website_url or None
        if payload.website_url:
            new_urls.append(payload.website_url)
    if payload.social_media_urls is not None and payload.social_media_urls != organization.social_media_urls:
        organization.social_media_urls = payload.social_media_urls or None
        if payload.social_media_urls:
            new_urls.extend([u.strip() for u in payload.social_media_urls.splitlines() if u.strip()])
    if payload.facebook_page_id is not None:
        organization.facebook_page_id = payload.facebook_page_id or None
    if payload.facebook_page_access_token is not None:
        organization.facebook_page_access_token = payload.facebook_page_access_token or None

    db.commit()

    if new_urls:
        sync_knowledge_source(db, organization, urls=new_urls)

    documents_count = db.query(KnowledgeDocument).filter(KnowledgeDocument.organization_id == organization_id).count()
    return OrganizationSourcesOut(
        website_url=organization.website_url, social_media_urls=organization.social_media_urls,
        documents_count=documents_count,
        facebook_page_id=organization.facebook_page_id,
        facebook_page_access_token=organization.facebook_page_access_token,
    )
