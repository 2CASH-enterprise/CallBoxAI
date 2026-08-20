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


def _build_pms_tools(organization_id: str, public_base_url: str) -> list[dict]:
    """
    Construit les outils "function calling" (section 16) que l'agent peut
    appeler EN DIRECT pendant l'appel pour consulter le PMS. organization_id
    est fixé une fois pour toutes ici (valeur "const", pas résolue par le
    LLM) : Retell ne connaît pas nos organisations, seule l'URL de l'outil
    encode celle concernée par cet agent précis.
    """
    base = public_base_url.rstrip("/")
    return [
        {
            "type": "custom",
            "name": "check_room_availability",
            "description": (
                "Vérifie la disponibilité et le tarif des chambres pour des dates données. "
                "Utilise ceci dès que le client demande une réservation ou une disponibilité."
            ),
            "url": f"{base}/pms/tools/availability?organization_id={organization_id}",
            "speak_during_execution": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "check_in": {"type": "string", "description": "Date d'arrivée au format AAAA-MM-JJ"},
                    "check_out": {"type": "string", "description": "Date de départ au format AAAA-MM-JJ"},
                    "room_type": {"type": "string", "description": "Type de chambre demandé (optionnel)"},
                },
                "required": ["check_in", "check_out"],
            },
        },
        {
            "type": "custom",
            "name": "create_room_reservation",
            "description": (
                "Crée réellement la réservation une fois que le client a confirmé les dates, "
                "le type de chambre, et donné son nom et son numéro de téléphone."
            ),
            "url": f"{base}/pms/tools/reservations?organization_id={organization_id}",
            "speak_during_execution": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "check_in": {"type": "string", "description": "Date d'arrivée au format AAAA-MM-JJ"},
                    "check_out": {"type": "string", "description": "Date de départ au format AAAA-MM-JJ"},
                    "room_type": {"type": "string", "description": "Type de chambre choisi"},
                    "guest_name": {"type": "string", "description": "Nom du client"},
                    "guest_phone": {"type": "string", "description": "Numéro de téléphone du client, format international"},
                    "guest_email": {"type": "string", "description": "Adresse email du client, pour l'envoi de la confirmation de réservation (optionnel si le client refuse de la donner)"},
                },
                "required": ["check_in", "check_out", "room_type", "guest_name", "guest_phone"],
            },
        },
        {
            "type": "custom",
            "name": "find_reservation",
            "description": (
                "Retrouve les réservations actives d'un client à partir de son numéro de téléphone, "
                "ou d'un numéro de confirmation s'il le connaît. Utilise ceci avant toute modification "
                "ou annulation — le client rappelle souvent sans avoir son numéro de confirmation en tête."
            ),
            "url": f"{base}/pms/tools/find-reservation?organization_id={organization_id}",
            "speak_during_execution": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_phone": {"type": "string", "description": "Numéro de téléphone du client, format international"},
                    "confirmation_number": {"type": "string", "description": "Numéro de confirmation si le client le connaît (optionnel)"},
                },
                "required": ["guest_phone"],
            },
        },
        {
            "type": "custom",
            "name": "modify_reservation",
            "description": (
                "Modifie les dates et/ou le type de chambre d'une réservation existante. "
                "Utilise find_reservation d'abord pour obtenir le numéro de confirmation exact. "
                "Vérifie automatiquement la disponibilité des nouvelles dates avant de confirmer."
            ),
            "url": f"{base}/pms/tools/modify-reservation?organization_id={organization_id}",
            "speak_during_execution": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Numéro de confirmation de la réservation à modifier"},
                    "new_check_in": {"type": "string", "description": "Nouvelle date d'arrivée au format AAAA-MM-JJ (optionnel si inchangée)"},
                    "new_check_out": {"type": "string", "description": "Nouvelle date de départ au format AAAA-MM-JJ (optionnel si inchangée)"},
                    "new_room_type": {"type": "string", "description": "Nouveau type de chambre (optionnel si inchangé)"},
                },
                "required": ["confirmation_number"],
            },
        },
        {
            "type": "custom",
            "name": "cancel_reservation",
            "description": (
                "Annule définitivement une réservation existante. Utilise find_reservation d'abord "
                "pour confirmer le bon numéro de réservation avec le client avant d'annuler."
            ),
            "url": f"{base}/pms/tools/cancel-reservation?organization_id={organization_id}",
            "speak_during_execution": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Numéro de confirmation de la réservation à annuler"},
                },
                "required": ["confirmation_number"],
            },
        },
    ]


class RetellProvider(VoiceProvider):
    def __init__(self, api_key: str, agent_id: str):
        self._agent_id = agent_id
        self._client = httpx.Client(
            base_url=RETELL_API_BASE,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )

    def create_llm(self, general_prompt: str, model: str, tools: list[dict] | None = None) -> dict:
        """Crée le "cerveau" LLM de l'agent côté Retell (prompt système, et outils éventuels)."""
        payload = {"model": model, "general_prompt": general_prompt}
        if tools:
            payload["general_tools"] = tools
        response = self._client.post("/create-retell-llm", json=payload)
        response.raise_for_status()
        return response.json()

    def create_retell_agent(self, name: str, llm_id: str, voice_id: str, language: str | None = None, webhook_url: str | None = None) -> dict:
        """
        Crée l'agent vocal côté Retell, attaché au LLM créé précédemment.
        webhook_url (section 16/30) : sans lui, Retell n'a AUCUN moyen de
        nous notifier la fin d'un appel réel — le webhook /webhooks/retell
        ne recevrait jamais rien, quel que soit le code qu'on y écrit.
        """
        payload = {
            "response_engine": {"type": "retell-llm", "llm_id": llm_id},
            "voice_id": voice_id,
            "agent_name": name,
        }
        if language:
            payload["language"] = language
        if webhook_url:
            payload["webhook_url"] = webhook_url
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

    def provision_agent(
        self,
        name: str,
        system_prompt: str,
        language: str,
        model: str,
        voice_id: str,
        pms_enabled: bool = False,
        organization_id: str | None = None,
        public_base_url: str | None = None,
    ) -> str:
        """
        Crée automatiquement, côté Retell, tout ce qu'il faut pour qu'un
        agent CallBoxAI soit réellement appelable : le LLM (prompt, outils
        éventuels), l'agent vocal (voix), puis le publie. Retourne
        l'agent_id Retell résultant.

        C'est cette méthode qui rend l'intégration Retell invisible pour le
        client final (section 1 : "AI Contact Center as a Service") — il n'a
        jamais besoin de connaître ni de manipuler le dashboard Retell.

        Si pms_enabled est vrai ET qu'une organization_id/public_base_url
        sont fournies, l'agent reçoit les outils de consultation/réservation
        PMS EN DIRECT pendant l'appel (section 16). Sans ces informations,
        l'agent se crée quand même, simplement sans ces outils — résilience
        (section 29), pas de blocage sur une configuration manquante.
        """
        tools = None
        if pms_enabled and organization_id and public_base_url:
            tools = _build_pms_tools(organization_id, public_base_url)

        webhook_url = f"{public_base_url.rstrip('/')}/webhooks/retell" if public_base_url else None

        llm = self.create_llm(
            general_prompt=system_prompt or f"Tu es {name}, un assistant vocal utile.", model=model, tools=tools
        )
        agent = self.create_retell_agent(
            name=name, llm_id=llm["llm_id"], voice_id=voice_id, language=_language_code(language), webhook_url=webhook_url
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
