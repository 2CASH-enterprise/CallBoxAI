"""
TwilioProvider — implémentation réelle de TelephonyProvider (section 16 du
cahier des charges), utilisant le SDK officiel Twilio.

N'est instancié et utilisé que si TELEPHONY_PROVIDER=twilio ET que les
identifiants (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER)
sont renseignés (voir app.core.providers). Tant que ce n'est pas le cas,
aucun appel réel — donc aucun coût — n'est jamais déclenché.

IMPORTANT : make_call() ici pointe vers une URL TwiML (`answer_url`) que
Twilio appelle pour savoir quoi faire une fois l'appel décroché (ex. relier
l'audio à Retell). Cette URL doit être publiquement accessible (HTTPS) —
c'est une pièce d'infrastructure à mettre en place lors du vrai déploiement,
au-delà de ce simple client API.
"""
from twilio.rest import Client

from app.providers.telephony.base import TelephonyProvider


class TwilioProvider(TelephonyProvider):
    def __init__(self, account_sid: str, auth_token: str, default_from_number: str, answer_url: str | None = None):
        self._client = Client(account_sid, auth_token)
        self._default_from_number = default_from_number
        # URL TwiML appelée par Twilio à la prise de ligne (ex. connecter à
        # Retell via <Stream>/<Dial><Sip>). À configurer au déploiement réel.
        self._answer_url = answer_url or "https://example.com/webhooks/twilio/answer"

    def make_call(self, to_number: str, from_number: str, agent_id: str) -> dict:
        call = self._client.calls.create(
            to=to_number,
            from_=from_number or self._default_from_number,
            url=self._answer_url,
        )
        return {
            "provider_call_id": call.sid,
            "status": call.status,
            "to": to_number,
            "from": from_number or self._default_from_number,
        }

    def hangup_call(self, provider_call_id: str) -> dict:
        call = self._client.calls(provider_call_id).update(status="completed")
        return {"provider_call_id": provider_call_id, "status": call.status}

    def transfer_call(self, provider_call_id: str, destination: str) -> dict:
        # Redirige l'appel en cours vers un nouveau TwiML qui compose le
        # numéro de destination (transfert, section 8/11 du cahier des charges).
        twiml = f'<Response><Dial>{destination}</Dial></Response>'
        call = self._client.calls(provider_call_id).update(twiml=twiml)
        return {"provider_call_id": provider_call_id, "status": call.status, "destination": destination}

    def get_call_status(self, provider_call_id: str) -> dict:
        call = self._client.calls(provider_call_id).fetch()
        return {"provider_call_id": provider_call_id, "status": call.status}
