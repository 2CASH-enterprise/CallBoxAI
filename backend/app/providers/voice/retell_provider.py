"""
RetellProvider — implémentation réelle de VoiceProvider (section 16 du
cahier des charges), contre l'API REST documentée de Retell
(https://docs.retellai.com/api-references/create-phone-call).

N'est instancié et utilisé que si VOICE_PROVIDER=retell ET que
RETELL_API_KEY/RETELL_AGENT_ID sont renseignés (voir app.core.providers).
Tant que ce n'est pas le cas, aucun appel réel — donc aucun coût — n'est
jamais déclenché.

Note d'architecture : côté Retell, un seul appel à /v2/create-phone-call
déclenche à la fois la téléphonie ET la conversation IA (Retell gère nativement
l'intégration Twilio pour les pays qu'il supporte). Notre séparation
TelephonyProvider / VoiceProvider reste utile pour les autres fournisseurs et
pour BYOC (opérateur local + Retell en mode "custom telephony", section 16),
mais avec l'intégration Retell native, start_conversation() est celle qui
déclenche réellement l'appel — make_call() de TelephonyProvider n'est alors
pas utilisé en parallèle pour éviter de déclencher l'appel deux fois.
"""
import httpx

from app.providers.voice.base import VoiceProvider

RETELL_API_BASE = "https://api.retellai.com"


class RetellProvider(VoiceProvider):
    def __init__(self, api_key: str, agent_id: str):
        self._agent_id = agent_id
        self._client = httpx.Client(
            base_url=RETELL_API_BASE,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )

    def create_phone_call(self, to_number: str, from_number: str) -> dict:
        """
        Déclenche réellement l'appel (téléphonie + IA en un seul appel API,
        voir note d'architecture ci-dessus). À utiliser à la place de
        TelephonyProvider.make_call() quand VOICE_PROVIDER=retell.
        """
        response = self._client.post(
            "/v2/create-phone-call",
            json={
                "from_number": from_number,
                "to_number": to_number,
                "override_agent_id": self._agent_id,
            },
        )
        response.raise_for_status()
        return response.json()

    def start_conversation(self, call_id: str, system_prompt: str) -> dict:
        # La conversation démarre dès la création de l'appel côté Retell
        # (create_phone_call) — cette méthode ne fait que confirmer l'état.
        return {"call_id": call_id, "status": "started"}

    def get_transcript(self, call_id: str) -> str:
        response = self._client.get(f"/v2/get-call/{call_id}")
        response.raise_for_status()
        data = response.json()
        return data.get("transcript", "")

    def get_summary(self, call_id: str) -> str:
        response = self._client.get(f"/v2/get-call/{call_id}")
        response.raise_for_status()
        data = response.json()
        analysis = data.get("call_analysis") or {}
        return analysis.get("call_summary", "")
