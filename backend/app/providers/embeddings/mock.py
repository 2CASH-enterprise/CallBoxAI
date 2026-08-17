"""
MockEmbeddingProvider — simule un fournisseur d'embeddings sans compte ni
clé API payante (section 40.3), via la technique du "feature hashing" :
chaque mot du texte est haché vers une position d'un vecteur de dimension
fixe, puis le vecteur est normalisé. Les textes qui partagent des mots
identiques obtiennent une similarité cosinus élevée — suffisant pour faire
fonctionner et tester tout le pipeline RAG (chunking -> embeddings ->
recherche par similarité) sans dépendre d'un vrai modèle d'embeddings.

À remplacer par un vrai fournisseur (ex. embeddings OpenAI/Claude/Cohere)
une fois la clé API disponible, sans changer le reste du pipeline.
"""
import hashlib
import math
import re

from app.providers.embeddings.base import EmbeddingProvider

_WORD_RE = re.compile(r"[a-zà-öø-ÿ0-9]+")


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 128):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        words = _WORD_RE.findall(text.lower())

        for word in words:
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]
