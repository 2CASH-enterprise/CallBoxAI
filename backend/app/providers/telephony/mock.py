"""
MockTelephonyProvider — simule un appel sans passer par Twilio (section 40.3).
Permet de tester tout le pipeline métier sans dépenser un centime.
"""
import uuid

from app.providers.telephony.base import TelephonyProvider


class MockTelephonyProvider(TelephonyProvider):
    def make_call(self, to_number: str, from_number: str, agent_id: str) -> dict:
        return {
            "provider_call_id": f"mock-{uuid.uuid4()}",
            "status": "in-progress",
            "to": to_number,
            "from": from_number,
        }

    def hangup_call(self, provider_call_id: str) -> dict:
        return {"provider_call_id": provider_call_id, "status": "completed"}

    def transfer_call(self, provider_call_id: str, destination: str) -> dict:
        return {"provider_call_id": provider_call_id, "status": "transferred", "destination": destination}

    def get_call_status(self, provider_call_id: str) -> dict:
        return {"provider_call_id": provider_call_id, "status": "completed"}
