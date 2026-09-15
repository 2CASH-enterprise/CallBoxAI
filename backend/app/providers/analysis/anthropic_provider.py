"""
Extraction réelle des informations pratiques d'un site web, via l'API
Anthropic (Claude) — outil interne de prospection, jamais utilisé côté
client.
"""
import anthropic

from app.providers.analysis.base import WebsiteAnalysisProvider

EXTRACTION_MODEL = "claude-haiku-4-5-20251001"

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
