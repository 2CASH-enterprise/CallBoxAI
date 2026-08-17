"""
Interface abstraite AnalyticsProvider (section 5 et 19 du cahier des charges).
Analyse un appel terminé (transcript, résumé, statut) et en tire une
classification exploitable : intent, qualification, sentiment, score,
action réalisée.
"""
from abc import ABC, abstractmethod


class AnalyticsProvider(ABC):
    @abstractmethod
    def classify(self, transcript: str, summary: str, status: str) -> dict:
        """
        Retourne un dict avec les clés : intent, qualification, sentiment,
        score (0-100), action_taken.
        """
        ...
