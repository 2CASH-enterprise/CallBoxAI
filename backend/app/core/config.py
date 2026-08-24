"""
Configuration centrale de l'application.
Toutes les valeurs sont lues depuis des variables d'environnement,
avec des valeurs par défaut adaptées au développement local
sans dépendance payante (voir section 40 du cahier des charges).
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Base de données : SQLite par défaut en dev/tests, Postgres en docker-compose/prod
    database_url: str = "sqlite:///./dev.db"

    # Sélection des providers (abstraction, section 5 du cahier des charges)
    # "mock" = simulation sans coût. En production : "twilio", "retell", etc.
    telephony_provider: str = "mock"
    voice_provider: str = "mock"
    messaging_provider: str = "mock"
    kyc_provider: str = "manual_review"

    # Identifiants des fournisseurs réels (section 16 du cahier des charges).
    # Vides par défaut : tant qu'ils ne sont pas renseignés ET que
    # telephony_provider/voice_provider ne valent pas "twilio"/"retell",
    # AUCUN appel réel n'est déclenché — donc AUCUN coût tant que vous ne
    # changez pas explicitement ces deux réglages en connaissance de cause.
    retell_api_key: str = ""
    retell_agent_id: str = ""
    # Utilisés uniquement pour la création AUTOMATIQUE d'agents (section 16) :
    # modèle LLM et voix par défaut appliqués à chaque agent créé côté Retell.
    # "cartesia-Emma" : voix francophone validée en conditions réelles comme
    # la plus naturelle pour ce cas d'usage (Sénégal/Congo-Brazzaville).
    # Chaque agent peut définir sa propre voix (Agent.voice_id) pour
    # remplacer ce réglage par défaut.
    retell_default_llm_model: str = "gpt-4o-mini"
    retell_default_voice_id: str = "cartesia-Emma"

    # URL publique de CE backend (ex. "http://178.104.56.200:8010"), utilisée
    # pour que Retell puisse appeler nos "outils" (function calling) EN DIRECT
    # pendant un vrai appel (section 16 — intégration PMS en temps réel).
    # Vide par défaut : sans elle, les outils PMS ne sont simplement pas
    # enregistrés côté Retell (résilience, section 29), pas d'erreur bloquante.
    public_base_url: str = ""

    # Email de confirmation (section 12/16) : Mailhog (docker-compose) par
    # défaut, sans compte ni coût. À remplacer par un vrai SMTP en production.
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_from_email: str = "reservations@callboxai.local"

    # Appel de démo public depuis la landing page (section 1) : agent_id
    # Retell de l'agent "CallBoxAI Démo" (créé et provisionné une fois via
    # le dashboard normal, comme n'importe quel autre agent), et numéro
    # Retell depuis lequel l'appel est passé. Vides par défaut : sans ces
    # deux valeurs, la démo publique est simplement désactivée plutôt que
    # de planter (résilience, section 29).
    demo_agent_retell_id: str = ""
    demo_from_number: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    environment: str = "development"

    # Clé de signature des tokens JWT (section 24 du cahier des charges).
    # IMPORTANT : valeur par défaut UNIQUEMENT pour le développement local.
    # En production, définir SECRET_KEY dans les variables d'environnement
    # avec une vraie valeur aléatoire et secrète (ex. `openssl rand -hex 32`).
    secret_key: str = "dev-secret-key-do-not-use-in-production-change-me"

    class Config:
        env_file = ".env"


settings = Settings()
