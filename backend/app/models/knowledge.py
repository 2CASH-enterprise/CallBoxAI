"""
Base de connaissances (section 10 du cahier des charges).

Pipeline : Documents -> Extraction -> Chunking -> Embeddings -> Vector Store
-> RAG -> Agent IA.

Note d'architecture : l'embedding est stocké en JSON (liste de flottants)
dans une colonne texte plutôt qu'un type vecteur natif Postgres (pgvector).
À l'échelle du MVP (quelques centaines/milliers de chunks par entreprise),
un calcul de similarité cosinus côté Python est largement suffisant et reste
100% compatible SQLite (donc testable sans coût, section 40). Migrer vers
pgvector + recherche ANN native est un axe d'optimisation pour l'échelle
(section 15/40.5), sans changer la forme des tables.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer

from app.core.database import Base
from app.models.distributor import GUID


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    title = Column(String, nullable=False)
    source_type = Column(String, default="text")  # text | txt_upload | (pdf/docx à venir)

    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey("knowledge_documents.id"), nullable=False)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=False)  # JSON : liste de flottants

    created_at = Column(DateTime, default=datetime.utcnow)
