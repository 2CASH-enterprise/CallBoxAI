"""
MockLeadProvider — utilisé en tests, ne fait aucun vrai appel réseau vers
l'API Graph de Meta.
"""
from app.providers.leads.base import LeadProvider
from app.providers.leads.facebook import _parse_field_data


class MockLeadProvider(LeadProvider):
    def __init__(self, canned_field_data: list[dict] | None = None):
        self._canned_field_data = canned_field_data or [
            {"name": "full_name", "values": ["Prospect Test"]},
            {"name": "phone_number", "values": ["+33612960001"]},
            {"name": "consentement_appel", "values": ["Oui, j'accepte d'être contacté par téléphone."]},
        ]

    def fetch_lead_details(self, leadgen_id: str, page_access_token: str) -> dict:
        return _parse_field_data(self._canned_field_data)
