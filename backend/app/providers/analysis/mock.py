"""
MockWebsiteAnalysisProvider — utilisé en tests, ne fait aucun appel réel à
un modèle de langage.
"""
from app.providers.analysis.base import WebsiteAnalysisProvider


class MockWebsiteAnalysisProvider(WebsiteAnalysisProvider):
    def extract_practical_info(self, website_text: str, company_name: str) -> str:
        return (
            f"[Résumé simulé pour {company_name}]\n"
            "Horaires : information non trouvée sur le site.\n"
            "Petit-déjeuner : information non trouvée sur le site.\n"
            "Parking : information non trouvée sur le site.\n"
            "Animaux : information non trouvée sur le site."
        )
