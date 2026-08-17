"""
Interface abstraite Voice AI (section 5 du cahier des charges).
"""
from abc import ABC, abstractmethod


class VoiceProvider(ABC):
    @abstractmethod
    def start_conversation(self, call_id: str, system_prompt: str) -> dict:
        ...

    @abstractmethod
    def get_transcript(self, call_id: str) -> str:
        ...

    @abstractmethod
    def get_summary(self, call_id: str) -> str:
        ...


class MockVoiceProvider(VoiceProvider):
    """Simule une conversation IA sans passer par Retell (section 40.3)."""

    def start_conversation(self, call_id: str, system_prompt: str) -> dict:
        return {"call_id": call_id, "status": "started"}

    def get_transcript(self, call_id: str) -> str:
        return (
            "Agent: Bonjour, comment puis-je vous aider ?\n"
            "Client: Je voudrais des informations sur vos services.\n"
            "Agent: Bien sûr, je vous transmets les détails."
        )

    def get_summary(self, call_id: str) -> str:
        return "Client intéressé, demande d'information générale traitée."
