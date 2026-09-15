"""
Extraction réelle des informations pratiques d'un site web, via l'API
Mistral AI (souveraineté française/européenne) — outil interne de
prospection, jamais utilisé côté client. Alternative à Anthropic, même
comportement garanti par le prompt partagé (voir app.providers.analysis.base).
"""
from mistralai import Mistral

from app.providers.analysis.base import WebsiteAnalysisProvider, EXTRACTION_SYSTEM_PROMPT

EXTRACTION_MODEL = "mistral-small-latest"


class MistralWebsiteAnalysisProvider(WebsiteAnalysisProvider):
    def __init__(self, api_key: str):
        self._client = Mistral(api_key=api_key)

    def extract_practical_info(self, website_text: str, company_name: str) -> str:
        # Limite de sécurité (section 29) : un site trop volumineux ne doit
        # jamais faire exploser le coût ou la taille de la requête.
        truncated_text = website_text[:40_000]

        response = self._client.chat.complete(
            model=EXTRACTION_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Entreprise : {company_name}\n\nContenu du site web :\n{truncated_text}"},
            ],
        )
        return response.choices[0].message.content
