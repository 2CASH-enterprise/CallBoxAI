"""
Recherche par similarité (RAG) — section 10 du cahier des charges.

Calcul de similarité cosinus effectué côté Python (voir la note dans
app/models/knowledge.py sur ce choix, adapté à l'échelle du MVP).
"""
import json
import math
import uuid

from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.providers.embeddings.base import EmbeddingProvider


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_top_chunks(
    db: Session,
    organization_id: uuid.UUID,
    query: str,
    embedding_provider: EmbeddingProvider,
    top_k: int = 3,
) -> list[dict]:
    """
    Retourne les `top_k` chunks les plus pertinents pour `query`, au sein de
    la base de connaissances de cette organisation (isolation stricte,
    section 3). Retourne une liste vide si l'organisation n'a aucun document.
    """
    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.organization_id == organization_id).all()
    if not chunks:
        return []

    query_vector = embedding_provider.embed(query)

    scored = []
    for chunk in chunks:
        chunk_vector = json.loads(chunk.embedding)
        score = cosine_similarity(query_vector, chunk_vector)
        scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[:top_k]

    document_titles = {
        d.id: d.title
        for d in db.query(KnowledgeDocument).filter(KnowledgeDocument.organization_id == organization_id).all()
    }

    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "document_title": document_titles.get(chunk.document_id, "Document"),
            "content": chunk.content,
            "score": round(score, 4),
        }
        for score, chunk in top
    ]
