"""
KeywordAnalyticsProvider — analyse RÉELLE du contenu de l'appel (section
19), par détection de marqueurs/mots-clés dans le vrai transcript. Utilisé
UNIQUEMENT pour les vrais appels (webhook, voir app.api.routes.webhooks) —
jamais pour les appels simulés, dont le transcript est lui-même fictif
(y appliquer une "vraie" analyse n'aurait aucun sens).

Approche volontairement par mots-clés plutôt que par LLM : gratuite,
déterministe, transparente (on peut expliquer chaque décision), sans
dépendance externe ni coût par appel. Moins subtile qu'un LLM, mais
directement fondée sur ce qui a été réellement dit — contrairement au
tirage aléatoire de MockAnalyticsProvider.

Signaux utilisés, par ordre de fiabilité (section 19/41) :
1. Action concrète confirmée (le plus fiable) — l'agent lui-même confirme
   dans sa réponse qu'un outil a réussi (réservation, lien KYC envoyé) :
   ce n'est pas une impression, c'est un fait qui s'est réellement produit.
2. Intention explicitement déclarée par le client (accepte/refuse/hésite).
3. Objections précises mentionnées (prix, concurrent déjà en place...).
4. Sentiment général, en dernier recours seulement si rien de plus précis
   n'a été détecté — un "ton" seul est le signal le moins fiable.
"""
from app.providers.analytics.base import AnalyticsProvider

# Marqueurs d'action concrète — l'agent confirme LUI-MÊME qu'un outil a
# réussi, formulation reprise de nos prompts d'agents (section 16/41).
RESERVATION_CONFIRMED_MARKERS = [
    "réservation est confirmée", "réservation confirmée", "numéro de confirmation",
]
KYC_SENT_MARKERS = [
    "lien de vérification d'identité", "lien kyc envoyé", "envoyé le lien kyc",
]

# Intention explicitement déclarée par le client.
POSITIVE_INTENT_PHRASES = [
    "je suis intéressé", "ça m'intéresse", "je veux activer", "je suis prêt",
    "d'accord pour", "je confirme", "oui je veux", "allons-y",
]
NEGATIVE_INTENT_PHRASES = [
    "pas intéressé", "non merci", "je ne veux pas", "pas besoin", "laissez tomber",
]
CALLBACK_PHRASES = [
    "rappelez-moi", "rappelle-moi", "je vais réfléchir", "pas maintenant",
    "plus tard", "je n'ai pas le temps",
]

# Objections précises — utile pour comprendre POURQUOI un prospect hésite,
# pas seulement QU'il hésite (section 19).
OBJECTION_PATTERNS = {
    "Prix": ["trop cher", "le prix", "coûte trop", "tarif élevé"],
    "Concurrent déjà en place": ["j'ai déjà", "je suis déjà chez", "déjà abonné", "déjà client"],
    "Pas de smartphone": ["pas de smartphone", "je n'ai pas de téléphone"],
}


def _count_matches(text: str, phrases: list[str]) -> int:
    return sum(1 for phrase in phrases if phrase in text)


class KeywordAnalyticsProvider(AnalyticsProvider):
    def classify(self, transcript: str, summary: str, status: str) -> dict:
        if status == "transferred":
            return {
                "intent": "Demande complexe",
                "qualification": "À suivre par un humain",
                "sentiment": "Neutre",
                "score": 50,
                "action_taken": "Transfert vers opérateur",
            }

        text = f"{transcript or ''} {summary or ''}".lower()

        objections = [name for name, phrases in OBJECTION_PATTERNS.items() if _count_matches(text, phrases) > 0]

        # 1. Action concrète confirmée — signal le plus fiable, prioritaire
        # sur tout le reste.
        if _count_matches(text, RESERVATION_CONFIRMED_MARKERS) > 0:
            return {
                "intent": "Prise de rendez-vous",
                "qualification": "Prospect chaud",
                "sentiment": "Positif",
                "score": 90,
                "action_taken": "Rendez-vous pris",
            }
        if _count_matches(text, KYC_SENT_MARKERS) > 0:
            return {
                "intent": "Prise de rendez-vous",
                "qualification": "Prospect chaud",
                "sentiment": "Positif",
                "score": 85,
                "action_taken": "Information transmise",
            }

        # 2. Intention explicitement déclarée
        positive_hits = _count_matches(text, POSITIVE_INTENT_PHRASES)
        negative_hits = _count_matches(text, NEGATIVE_INTENT_PHRASES)
        callback_hits = _count_matches(text, CALLBACK_PHRASES)

        intent = "Réclamation" if objections else "Demande d'information"

        if negative_hits > 0 and positive_hits == 0:
            return {
                "intent": intent, "qualification": "Pas intéressé", "sentiment": "Négatif",
                "score": 15, "action_taken": "Aucune action",
            }
        if callback_hits > 0:
            return {
                "intent": intent, "qualification": "Prospect tiède", "sentiment": "Neutre",
                "score": 45, "action_taken": "Rappel programmé",
            }
        if positive_hits > 0:
            return {
                "intent": intent, "qualification": "Prospect chaud", "sentiment": "Positif",
                "score": 70, "action_taken": "Information transmise",
            }

        # 3. Aucun signal clair détecté — ni positif, ni négatif, ni rappel.
        # Reste prudent plutôt que d'inventer une conclusion.
        return {
            "intent": intent, "qualification": "Prospect tiède", "sentiment": "Neutre",
            "score": 40, "action_taken": "Information transmise",
        }
