"""
Interface abstraite EmbeddingProvider (section 5 du cahier des charges).
Aucune logique métier ne doit dépendre directement d'un fournisseur
d'embeddings particulier : elle ne doit connaître que cette interface.
"""
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Retourne un vecteur numérique représentant le texte."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...
