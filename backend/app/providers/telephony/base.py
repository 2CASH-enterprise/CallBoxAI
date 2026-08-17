"""
Interface abstraite Telephony (section 5 du cahier des charges).
Aucune logique métier ne doit dépendre directement de Twilio :
elle ne doit connaitre que cette interface.
"""
from abc import ABC, abstractmethod
from typing import Optional


class TelephonyProvider(ABC):
    @abstractmethod
    def make_call(self, to_number: str, from_number: str, agent_id: str) -> dict:
        """Déclenche un appel sortant. Retourne un dict avec provider_call_id, status."""
        ...

    @abstractmethod
    def hangup_call(self, provider_call_id: str) -> dict:
        ...

    @abstractmethod
    def transfer_call(self, provider_call_id: str, destination: str) -> dict:
        ...

    @abstractmethod
    def get_call_status(self, provider_call_id: str) -> dict:
        ...
