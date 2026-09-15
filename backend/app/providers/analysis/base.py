"""
Interface abstraite pour l'analyse automatique d'un site web (outil interne
de prospection, jamais visible des clients) — extrait les informations
pratiques utiles à un futur agent vocal (horaires, politiques, équipements...).
"""
from abc import ABC, abstractmethod


class WebsiteAnalysisProvider(ABC):
    @abstractmethod
    def extract_practical_info(self, website_text: str, company_name: str) -> str:
        """
        Retourne un résumé structuré, en français, des informations
        pratiques trouvées dans le texte — jamais d'invention : doit
        indiquer explicitement quand une information n'est pas trouvée.
        """
        ...
