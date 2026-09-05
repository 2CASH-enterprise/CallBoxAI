"""
Récupération réelle du détail d'un lead via l'API Graph de Meta (section
42/43). Le webhook Facebook ne transmet qu'un identifiant (leadgen_id) —
il faut un second appel pour obtenir les vraies réponses du formulaire
(nom, téléphone, réponse à la question de consentement...).
"""
import httpx

from app.providers.leads.base import LeadProvider

GRAPH_API_VERSION = "v21.0"

# Noms de champs les plus courants utilisés par Meta pour le téléphone/nom
# dans un formulaire Lead Ads standard — les champs personnalisés (comme la
# question de consentement) varient selon la configuration du formulaire,
# d'où la conservation de la réponse brute complète en plus.
PHONE_FIELD_NAMES = {"phone_number", "phone"}
NAME_FIELD_NAMES = {"full_name", "first_name"}


class FacebookLeadProvider(LeadProvider):
    def fetch_lead_details(self, leadgen_id: str, page_access_token: str) -> dict:
        response = httpx.get(
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{leadgen_id}",
            params={"access_token": page_access_token},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        return _parse_field_data(data.get("field_data", []))


def _parse_field_data(field_data: list[dict]) -> dict:
    phone, name = None, None
    summary_parts = []
    for field in field_data:
        field_name = field.get("name", "")
        values = field.get("values", [])
        value = values[0] if values else None
        summary_parts.append(f"{field_name}: {value}")
        if field_name in PHONE_FIELD_NAMES and value:
            phone = value
        if field_name in NAME_FIELD_NAMES and value and not name:
            name = value

    return {
        "phone": phone,
        "name": name,
        "field_data": field_data,
        "raw_field_summary": " | ".join(summary_parts),
    }
