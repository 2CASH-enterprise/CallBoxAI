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

# Correspondance entre les langues de la plateforme (section 8) et les codes
# de langue attendus par Retell. Le wolof n'a pas de support TTS/STT connu
# chez Retell à ce jour : on retombe sur le français plutôt que d'échouer.
# "multi" active la détection automatique de langue de Retell (confirmé sur
# leur documentation officielle : 55 langues supportées, bascule automatique
# selon ce que dit l'appelant) — la qualité perçue dépend cependant de la
# voix choisie, certaines voix étant optimisées pour une langue en particulier.
_LANGUAGE_CODES = {
    "fr": "fr-FR",
    "en": "en-US",
    "wo": "fr-FR",
    "multi": "multi",
}


def _language_code(language: str) -> str:
    return _LANGUAGE_CODES.get(language, "fr-FR")


class RetellProvider(VoiceProvider):
    def __init__(self, api_key: str, agent_id: str):
        self._agent_id = agent_id
        self._client = httpx.Client(
            base_url=RETELL_API_BASE,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )

    def create_llm(self, general_prompt: str, model: str) -> dict:
        """Crée le "cerveau" LLM de l'agent côté Retell (prompt système)."""
        response = self._client.post(
            "/create-retell-llm",
            json={"model": model, "general_prompt": general_prompt},
        )
        response.raise_for_status()
        return response.json()

    def create_retell_agent(self, name: str, llm_id: str, voice_id: str, language: str | None = None) -> dict:
        """Crée l'agent vocal côté Retell, attaché au LLM créé précédemment."""
        payload = {
            "response_engine": {"type": "retell-llm", "llm_id": llm_id},
            "voice_id": voice_id,
            "agent_name": name,
        }
        if language:
            payload["language"] = language
        response = self._client.post("/create-agent", json=payload)
        response.raise_for_status()
        return response.json()

    def publish_agent(self, agent_id: str) -> dict:
        """Publie la dernière version de l'agent pour la rendre effectivement appelable."""
        response = self._client.post(f"/publish-agent/{agent_id}")
        response.raise_for_status()
        # Certaines réponses de succès de cet endpoint arrivent sans corps
        # (ou avec un corps non-JSON) — on ne bloque pas là-dessus, la
        # valeur de retour n'est de toute façon pas utilisée par provision_agent.
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    def provision_agent(self, name: str, system_prompt: str, language: str, model: str, voice_id: str) -> str:
        """
        Crée automatiquement, côté Retell, tout ce qu'il faut pour qu'un
        agent CallBoxAI soit réellement appelable : le LLM (prompt), l'agent
        vocal (voix), puis le publie. Retourne l'agent_id Retell résultant.

        C'est cette méthode qui rend l'intégration Retell invisible pour le
        client final (section 1 : "AI Contact Center as a Service") — il n'a
        jamais besoin de connaître ni de manipuler le dashboard Retell.
        """
        llm = self.create_llm(general_prompt=system_prompt or f"Tu es {name}, un assistant vocal utile.", model=model)
        agent = self.create_retell_agent(
            name=name, llm_id=llm["llm_id"], voice_id=voice_id, language=_language_code(language)
        )
        self.publish_agent(agent["agent_id"])
        return agent["agent_id"]

    def create_web_call(self, agent_id: str | None = None) -> dict:
        """
        Crée une session d'appel Web (WebRTC, section 16) : permet de tester
        la conversation vocale en direct depuis le navigateur, sans passer
        par un numéro de téléphone ni par Twilio. Retourne notamment un
        access_token à utiliser côté frontend avec le SDK Web de Retell.
        """
        response = self._client.post(
            "/v2/create-web-call",
            json={"agent_id": agent_id or self._agent_id},
        )
        response.raise_for_status()
        return response.json()

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
