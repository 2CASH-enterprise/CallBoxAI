"""
Fabrique de providers (section 5 du cahier des charges) : choisit
l'implémentation Mock ou réelle selon la configuration, sans que le reste du
code métier (routes, pipeline d'appel) n'ait à s'en soucier.

Sécurité par défaut : si un provider "réel" est demandé (TELEPHONY_PROVIDER
ou VOICE_PROVIDER) mais que les identifiants correspondants sont absents,
on retombe sur le Mock plutôt que de planter au démarrage — pour ne jamais
bloquer accidentellement le développement local à cause d'une variable
d'environnement oubliée.
"""
from app.core.config import settings
from app.providers.telephony.base import TelephonyProvider
from app.providers.telephony.mock import MockTelephonyProvider
from app.providers.voice.base import VoiceProvider
from app.providers.voice.mock import MockVoiceProvider
from app.providers.messaging.base import MessagingProvider
from app.providers.messaging.mock import MockMessagingProvider


def get_telephony_provider() -> TelephonyProvider:
    if settings.telephony_provider == "twilio" and settings.twilio_account_sid and settings.twilio_auth_token:
        from app.providers.telephony.twilio_provider import TwilioProvider

        return TwilioProvider(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            default_from_number=settings.twilio_phone_number,
        )
    return MockTelephonyProvider()


def get_voice_provider() -> VoiceProvider:
    if settings.voice_provider == "retell" and settings.retell_api_key and settings.retell_agent_id:
        from app.providers.voice.retell_provider import RetellProvider

        return RetellProvider(api_key=settings.retell_api_key, agent_id=settings.retell_agent_id)
    return MockVoiceProvider()


def get_messaging_provider(db, organization_id) -> MessagingProvider:
    """
    Contrairement aux autres providers, celui-ci a besoin d'une session DB et
    de l'organisation concernée — le Mock journalise le SMS dans SmsLog
    (page "SMS" du dashboard) au lieu de l'envoyer réellement.
    """
    if settings.messaging_provider == "twilio" and settings.twilio_account_sid and settings.twilio_auth_token:
        from app.providers.messaging.twilio_provider import TwilioMessagingProvider

        return TwilioMessagingProvider(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            from_number=settings.twilio_phone_number,
        )
    return MockMessagingProvider(db=db, organization_id=organization_id)
