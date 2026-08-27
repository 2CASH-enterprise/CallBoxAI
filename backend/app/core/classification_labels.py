"""
Habillage du vocabulaire de classification selon le métier de l'agent
(section 19 et 41 du cahier des charges) — "Prospect tiède" n'a aucun sens
pour un client d'hôtel qui demande l'heure du petit-déjeuner.

IMPORTANT : ce module ne touche JAMAIS aux valeurs utilisées par la
logique métier (mise à jour du CRM, déclenchement d'un rendez-vous,
relances de campagne...) — celle-ci continue de raisonner sur le
vocabulaire canonique produit par AnalyticsProvider.classify(), inchangé.
Seul ce qui est ÉCRIT et AFFICHÉ (Call.intent/qualification/action_taken,
Ticket.category) est traduit, une fois la décision métier déjà prise.
"""

# "generique" et "prospection" ne sont pas listés : le vocabulaire canonique
# du classifieur EST déjà celui de la prospection commerciale, donc aucune
# traduction n'est nécessaire pour ces deux catégories.
CATEGORY_LABELS: dict[str, dict[str, dict[str, str]]] = {
    "hotellerie": {
        "intent": {
            "Demande d'information": "Demande d'information",
            "Demande de prix": "Demande de tarif",
            "Prise de rendez-vous": "Réservation",
            "Réclamation": "Réclamation",
            "Support technique": "Assistance",
            "Demande complexe": "Demande complexe",
        },
        "qualification": {
            "Prospect chaud": "Client satisfait",
            "Prospect tiède": "Client à suivre",
            "Pas intéressé": "Client insatisfait",
            "À suivre par un humain": "À suivre par un humain",
        },
        "action_taken": {
            "Rendez-vous pris": "Réservation prise",
            "Rappel programmé": "Rappel programmé",
            "Information transmise": "Information transmise",
            "Aucune action": "Aucune action",
            "Transfert vers opérateur": "Transfert vers opérateur",
            "Message pris": "Message pris",
        },
    },
    "service_client": {
        "intent": {
            "Demande d'information": "Demande d'information",
            "Demande de prix": "Question sur facturation",
            "Prise de rendez-vous": "Prise de rendez-vous",
            "Réclamation": "Réclamation",
            "Support technique": "Support technique",
            "Demande complexe": "Demande complexe",
        },
        "qualification": {
            "Prospect chaud": "Résolu",
            "Prospect tiède": "En cours de résolution",
            "Pas intéressé": "Non résolu",
            "À suivre par un humain": "À suivre par un humain",
        },
        "action_taken": {
            "Rendez-vous pris": "Rendez-vous pris",
            "Rappel programmé": "Rappel programmé",
            "Information transmise": "Information transmise",
            "Aucune action": "Aucune action",
            "Transfert vers opérateur": "Transfert vers opérateur",
            "Message pris": "Message pris",
        },
    },
    "telesecretariat": {
        "intent": {
            "Demande d'information": "Demande d'information",
            "Demande de prix": "Demande de tarif",
            "Prise de rendez-vous": "Prise de rendez-vous",
            "Réclamation": "Réclamation",
            "Support technique": "Support technique",
            "Demande complexe": "Demande complexe",
        },
        "qualification": {
            "Prospect chaud": "Contact favorable",
            "Prospect tiède": "À rappeler",
            "Pas intéressé": "Sans suite",
            "À suivre par un humain": "À suivre par un humain",
        },
        "action_taken": {
            "Rendez-vous pris": "Rendez-vous pris",
            "Rappel programmé": "Rappel programmé",
            "Information transmise": "Information transmise",
            "Aucune action": "Aucune action",
            "Transfert vers opérateur": "Transfert vers opérateur",
            "Message pris": "Message pris",
        },
    },
    "telecom": {
        "intent": {
            "Demande d'information": "Demande d'information",
            "Demande de prix": "Demande sur une offre",
            "Prise de rendez-vous": "Activation programmée",
            "Réclamation": "Réclamation",
            "Support technique": "Support technique",
            "Demande complexe": "Demande complexe",
        },
        "qualification": {
            "Prospect chaud": "Prêt à activer",
            "Prospect tiède": "À relancer",
            "Pas intéressé": "Sans suite",
            "À suivre par un humain": "À suivre par un humain",
        },
        "action_taken": {
            "Rendez-vous pris": "Activation programmée",
            "Rappel programmé": "Relance programmée",
            "Information transmise": "Information transmise",
            "Aucune action": "Aucune action",
            "Transfert vers opérateur": "Transfert vers opérateur",
            "Message pris": "Message pris",
        },
    },
    "fidelisation": {
        "intent": {
            "Demande d'information": "Demande d'information",
            "Demande de prix": "Demande sur une offre",
            "Prise de rendez-vous": "Intérêt confirmé",
            "Réclamation": "Réclamation",
            "Support technique": "Support technique",
            "Demande complexe": "Demande complexe",
        },
        "qualification": {
            "Prospect chaud": "Intéressé",
            "Prospect tiède": "À recontacter",
            "Pas intéressé": "Pas intéressé",
            "À suivre par un humain": "À suivre par un humain",
        },
        "action_taken": {
            "Rendez-vous pris": "Intérêt confirmé",
            "Rappel programmé": "Relance programmée",
            "Information transmise": "Information transmise",
            "Aucune action": "Aucune action",
            "Transfert vers opérateur": "Transfert vers opérateur",
            "Message pris": "Message pris",
        },
    },
}


def localize_classification(classification: dict, category: str) -> dict:
    """
    Retourne une COPIE de la classification avec intent/qualification/
    action_taken traduits selon la catégorie de l'agent, pour l'affichage
    uniquement. `sentiment` et `score` ne dépendent d'aucun vocabulaire
    métier et ne sont jamais modifiés.
    """
    labels = CATEGORY_LABELS.get(category)
    if not labels:
        return dict(classification)

    localized = dict(classification)
    for field in ("intent", "qualification", "action_taken"):
        value = classification.get(field)
        if value is not None:
            localized[field] = labels.get(field, {}).get(value, value)
    return localized
