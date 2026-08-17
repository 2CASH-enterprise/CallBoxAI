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

    environment: str = "development"

    # Clé de signature des tokens JWT (section 24 du cahier des charges).
    # IMPORTANT : valeur par défaut UNIQUEMENT pour le développement local.
    # En production, définir SECRET_KEY dans les variables d'environnement
    # avec une vraie valeur aléatoire et secrète (ex. `openssl rand -hex 32`).
    secret_key: str = "dev-secret-key-do-not-use-in-production-change-me"

    class Config:
        env_file = ".env"


settings = Settings()
