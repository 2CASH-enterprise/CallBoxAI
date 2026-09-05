"""
Interface abstraite pour la récupération du détail d'un lead entrant
(section 42/43 — Facebook Lead Ads, point 3/3 de la brique de compliance).
"""
from abc import ABC, abstractmethod


class LeadProvider(ABC):
    @abstractmethod
    def fetch_lead_details(self, leadgen_id: str, page_access_token: str) -> dict:
        """
        Retourne {"phone": str|None, "name": str|None, "field_data": list[dict],
        "raw_field_summary": str} — doit lever une exception si l'appel échoue.
        """
        ...
