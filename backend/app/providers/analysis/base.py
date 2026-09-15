"""
Interface abstraite pour l'analyse automatique d'un site web (outil interne
de prospection, jamais visible des clients) — extrait les informations
pratiques utiles à un futur agent vocal (horaires, politiques, équipements...).
"""
from abc import ABC, abstractmethod

# Partagé entre tous les fournisseurs (Anthropic, Mistral...) — garantit un
# comportement identique quel que soit le modèle de langage réellement
# utilisé derrière.
EXTRACTION_SYSTEM_PROMPT = (
    "Tu extrais les informations pratiques d'un site web d'entreprise, pour "
    "préparer la fiche de connaissance d'un futur agent vocal IA qui répondra "
    "au téléphone à la place de cette entreprise. Organise ta réponse en "
    "sections claires : Horaires, Tarifs/Chambres (si hôtel), Petit-déjeuner, "
    "Parking, Animaux, Équipements, Politiques (annulation, arrivée tardive...), "
    "Coordonnées, Autres informations pratiques. "
    "RÈGLE ABSOLUE : n'invente JAMAIS une information absente du texte fourni — "
    "écris explicitement \"information non trouvée sur le site\" pour toute "
    "section sans donnée correspondante. Réponds uniquement avec ce résumé, "
    "en français, sans préambule ni commentaire."
)


class WebsiteAnalysisProvider(ABC):
    @abstractmethod
    def extract_practical_info(self, website_text: str, company_name: str) -> str:
        """
        Retourne un résumé structuré, en français, des informations
        pratiques trouvées dans le texte — jamais d'invention : doit
        indiquer explicitement quand une information n'est pas trouvée.
        """
        ...
