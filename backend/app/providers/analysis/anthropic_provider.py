"""
Extraction réelle des informations pratiques d'un site web, via l'API
Anthropic (Claude) — outil interne de prospection, jamais utilisé côté
client.
"""
import anthropic

from app.providers.analysis.base import WebsiteAnalysisProvider, EXTRACTION_SYSTEM_PROMPT

EXTRACTION_MODEL = "claude-haiku-4-5-20251001"


class AnthropicWebsiteAnalysisProvider(WebsiteAnalysisProvider):
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def extract_practical_info(self, website_text: str, company_name: str) -> str:
        # Limite de sécurité (section 29) : un site trop volumineux ne doit
        # jamais faire exploser le coût ou la taille de la requête.
        truncated_text = website_text[:40_000]

        response = self._client.messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=1200,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Entreprise : {company_name}\n\nContenu du site web :\n{truncated_text}",
            }],
        )
        return "".join(block.text for block in response.content if hasattr(block, "text"))
