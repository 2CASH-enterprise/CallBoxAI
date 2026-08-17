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
    # "retell-Cimo" est une voix anglophone de démonstration — à remplacer par
    # une voix francophone disponible dans votre compte Retell (onglet
    # "Voices" du dashboard) avant toute mise en production réelle.
    retell_default_llm_model: str = "gpt-4o-mini"
    retell_default_voice_id: str = "retell-Cimo"
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
