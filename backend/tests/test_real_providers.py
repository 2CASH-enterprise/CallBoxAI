"""
Tests des implémentations RÉELLES de RetellProvider/TwilioProvider — sans
JAMAIS appeler les vraies API. Toutes les requêtes HTTP/SDK sont interceptées
et simulées (unittest.mock), donc ces tests ne coûtent rien et ne nécessitent
aucun compte ni clé API valide.
"""
from unittest.mock import MagicMock, patch

from app.core.providers import get_telephony_provider, get_voice_provider
from app.core.config import Settings
from app.providers.telephony.mock import MockTelephonyProvider
from app.providers.voice.mock import MockVoiceProvider


# ---------- Fabrique de providers : sécurité par défaut ----------

def test_factory_returns_mock_by_default():
    s = Settings(telephony_provider="mock", voice_provider="mock")
    with patch("app.core.providers.settings", s):
        assert isinstance(get_telephony_provider(), MockTelephonyProvider)
        assert isinstance(get_voice_provider(), MockVoiceProvider)


def test_factory_falls_back_to_mock_when_twilio_requested_without_credentials():
    """
    Sécurité critique : si TELEPHONY_PROVIDER=twilio est mis mais que les
    identifiants sont vides (oubliés), on ne doit JAMAIS planter ni,
    surtout, tenter un vrai appel — on retombe sur le Mock.
    """
    s = Settings(telephony_provider="twilio", twilio_account_sid="", twilio_auth_token="")
    with patch("app.core.providers.settings", s):
        assert isinstance(get_telephony_provider(), MockTelephonyProvider)


def test_factory_falls_back_to_mock_when_retell_requested_without_credentials():
    s = Settings(voice_provider="retell", retell_api_key="", retell_agent_id="")
    with patch("app.core.providers.settings", s):
        assert isinstance(get_voice_provider(), MockVoiceProvider)


def test_factory_returns_real_twilio_provider_when_configured(monkeypatch):
    """Avec des identifiants présents, la fabrique renvoie bien TwilioProvider (pas Mock)."""
    s = Settings(telephony_provider="twilio", twilio_account_sid="ACfake", twilio_auth_token="fake", twilio_phone_number="+15550000000")
    with patch("app.core.providers.settings", s):
        with patch("app.providers.telephony.twilio_provider.Client") as MockClient:
            MockClient.return_value = MagicMock()
            from app.providers.telephony.twilio_provider import TwilioProvider

            provider = get_telephony_provider()
            assert isinstance(provider, TwilioProvider)


# ---------- TwilioProvider : vérifie le contenu des requêtes, pas le réseau ----------

@patch("app.providers.telephony.twilio_provider.Client")
def test_twilio_provider_make_call_builds_correct_request(MockClient):
    from app.providers.telephony.twilio_provider import TwilioProvider

    mock_call = MagicMock(sid="CAfake123", status="queued")
    mock_client_instance = MagicMock()
    mock_client_instance.calls.create.return_value = mock_call
    MockClient.return_value = mock_client_instance

    provider = TwilioProvider(account_sid="ACfake", auth_token="fake", default_from_number="+15550000000")
    result = provider.make_call(to_number="+221770000000", from_number="+15550000000", agent_id="agent-1")

    # Vérifie que le SDK a été appelé avec les bons paramètres — AUCUNE requête réseau réelle
    mock_client_instance.calls.create.assert_called_once()
    _, kwargs = mock_client_instance.calls.create.call_args
    assert kwargs["to"] == "+221770000000"
    assert kwargs["from_"] == "+15550000000"

    assert result["provider_call_id"] == "CAfake123"
    assert result["status"] == "queued"


@patch("app.providers.telephony.twilio_provider.Client")
def test_twilio_provider_transfer_call(MockClient):
    from app.providers.telephony.twilio_provider import TwilioProvider

    mock_call_resource = MagicMock()
    mock_call_resource.update.return_value = MagicMock(status="in-progress")
    mock_client_instance = MagicMock()
    mock_client_instance.calls.return_value = mock_call_resource
    MockClient.return_value = mock_client_instance

    provider = TwilioProvider(account_sid="ACfake", auth_token="fake", default_from_number="+15550000000")
    result = provider.transfer_call("CAfake123", "+221339000000")

    mock_call_resource.update.assert_called_once()
    _, kwargs = mock_call_resource.update.call_args
    assert "+221339000000" in kwargs["twiml"]
    assert result["destination"] == "+221339000000"


# ---------- RetellProvider : vérifie le contenu des requêtes, pas le réseau ----------

@patch("httpx.Client.post")
def test_retell_provider_create_phone_call_builds_correct_request(mock_post):
    from app.providers.voice.retell_provider import RetellProvider

    mock_response = MagicMock()
    mock_response.json.return_value = {"call_id": "call_fake123", "call_status": "registered"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    provider = RetellProvider(api_key="fake_key", agent_id="agent_fake")
    result = provider.create_phone_call(to_number="+221770000000", from_number="+15550000000")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "/v2/create-phone-call"
    assert kwargs["json"]["to_number"] == "+221770000000"
    assert kwargs["json"]["override_agent_id"] == "agent_fake"

    assert result["call_id"] == "call_fake123"


@patch("httpx.Client.get")
def test_retell_provider_get_transcript_and_summary(mock_get):
    from app.providers.voice.retell_provider import RetellProvider

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "transcript": "Agent: Bonjour...\nClient: Bonjour...",
        "call_analysis": {"call_summary": "Client intéressé par une démo."},
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    provider = RetellProvider(api_key="fake_key", agent_id="agent_fake")

    assert "Bonjour" in provider.get_transcript("call_fake123")
    assert provider.get_summary("call_fake123") == "Client intéressé par une démo."
    mock_get.assert_called()
