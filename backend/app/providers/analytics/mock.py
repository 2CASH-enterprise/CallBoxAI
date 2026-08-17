"""
MockAnalyticsProvider — simule la classification d'un appel (intent,
sentiment, qualification, score) sans clé API LLM (section 40.3). Une
conversation transférée vers un humain est classifiée de façon déterministe
(utile pour les tests) ; les autres suivent une distribution pondérée
réaliste plutôt qu'un tirage uniforme.

À remplacer par un vrai classifieur (appel LLM) une fois une clé API
disponible, sans changer le reste du pipeline (section 5).
"""
import random

from app.providers.analytics.base import AnalyticsProvider

INTENTS = [
    "Demande d'information",
    "Demande de prix",
    "Prise de rendez-vous",
    "Réclamation",
    "Support technique",
]

SENTIMENTS = ["Positif", "Neutre", "Négatif"]


class MockAnalyticsProvider(AnalyticsProvider):
    def classify(self, transcript: str, summary: str, status: str) -> dict:
        if status == "transferred":
            return {
                "intent": "Demande complexe",
                "qualification": "À suivre par un humain",
                "sentiment": "Neutre",
                "score": 50,
                "action_taken": "Transfert vers opérateur",
            }

        sentiment = random.choices(SENTIMENTS, weights=[60, 30, 10])[0]
        intent = random.choice(INTENTS)

        if sentiment == "Positif":
            qualification = random.choices(["Prospect chaud", "Prospect tiède"], weights=[70, 30])[0]
        elif sentiment == "Neutre":
            qualification = random.choices(["Prospect tiède", "Pas intéressé"], weights=[70, 30])[0]
        else:
            qualification = "Pas intéressé"

        if qualification == "Prospect chaud":
            score = random.randint(75, 95)
            action_taken = random.choices(["Rendez-vous pris", "Rappel programmé"], weights=[60, 40])[0]
        elif qualification == "Prospect tiède":
            score = random.randint(45, 74)
            action_taken = random.choices(["Information transmise", "Rappel programmé"], weights=[70, 30])[0]
        else:
            score = random.randint(10, 44)
            action_taken = "Aucune action"

        return {
            "intent": intent,
            "qualification": qualification,
            "sentiment": sentiment,
            "score": score,
            "action_taken": action_taken,
        }
