"""
Tests du vrai classifieur (section 19), basé sur des marqueurs détectés
dans le transcript réel — pas un tirage aléatoire. Chaque test vérifie
qu'un signal précis dans le texte produit la bonne conclusion.
"""
from app.providers.analytics.keyword import KeywordAnalyticsProvider

provider = KeywordAnalyticsProvider()


def test_transferred_status_is_always_deterministic():
    result = provider.classify(transcript="peu importe le contenu", summary="", status="transferred")
    assert result["qualification"] == "À suivre par un humain"
    assert result["action_taken"] == "Transfert vers opérateur"


def test_confirmed_reservation_marker_produces_hot_prospect():
    """Signal le plus fiable : l'agent confirme lui-même qu'une vraie réservation a été faite."""
    transcript = "Agent: Votre réservation est confirmée pour le 20 septembre. Votre numéro de confirmation est MOCK-ABC123."
    result = provider.classify(transcript=transcript, summary="", status="completed")
    assert result["qualification"] == "Prospect chaud"
    assert result["action_taken"] == "Rendez-vous pris"
    assert result["score"] >= 85


def test_kyc_sent_marker_produces_hot_prospect_without_fake_appointment():
    """
    Distinction importante : l'envoi du lien KYC doit rester "Prospect chaud"
    mais SANS action_taken="Rendez-vous pris" (éviterait de déclencher la
    création d'un faux rendez-vous générique pour un agent non-PMS).
    """
    transcript = "Agent: J'ai envoyé le lien de vérification d'identité (KYC) par SMS à votre numéro."
    result = provider.classify(transcript=transcript, summary="", status="completed")
    assert result["qualification"] == "Prospect chaud"
    assert result["action_taken"] != "Rendez-vous pris"


def test_positive_intent_without_concrete_action():
    transcript = "Client: Oui, ça m'intéresse beaucoup, je suis prêt à avancer."
    result = provider.classify(transcript=transcript, summary="", status="completed")
    assert result["qualification"] == "Prospect chaud"
    assert result["sentiment"] == "Positif"


def test_negative_intent_produces_not_interested():
    transcript = "Client: Non merci, je ne suis pas intéressé, laissez tomber."
    result = provider.classify(transcript=transcript, summary="", status="completed")
    assert result["qualification"] == "Pas intéressé"
    assert result["sentiment"] == "Négatif"
    assert result["action_taken"] == "Aucune action"


def test_callback_request_produces_warm_prospect_with_followup_action():
    transcript = "Client: Je vais réfléchir, rappelez-moi la semaine prochaine."
    result = provider.classify(transcript=transcript, summary="", status="completed")
    assert result["qualification"] == "Prospect tiède"
    assert result["action_taken"] == "Rappel programmé"


def test_price_objection_detected_and_reflected_in_intent():
    transcript = "Client: C'est trop cher pour moi, le prix ne me convient pas. Je vais réfléchir."
    result = provider.classify(transcript=transcript, summary="", status="completed")
    assert result["intent"] == "Réclamation"


def test_no_clear_signal_stays_cautious_not_invented():
    """Sans signal net, le classifieur ne doit jamais inventer une conclusion tranchée."""
    transcript = "Agent: Bonjour. Client: Bonjour, il fait beau aujourd'hui."
    result = provider.classify(transcript=transcript, summary="", status="completed")
    assert result["qualification"] == "Prospect tiède"
    assert 30 <= result["score"] <= 50


def test_concrete_action_wins_over_negative_wording_elsewhere_in_transcript():
    """L'action concrète confirmée doit primer, même si d'autres phrases semblent négatives."""
    transcript = (
        "Client: Au début je n'étais pas intéressé, mais finalement, votre réservation est confirmée, "
        "numéro de confirmation MOCK-XYZ."
    )
    result = provider.classify(transcript=transcript, summary="", status="completed")
    assert result["qualification"] == "Prospect chaud"
    assert result["action_taken"] == "Rendez-vous pris"


def test_classification_reads_summary_too_not_only_transcript():
    result = provider.classify(transcript="", summary="Le client a confirmé son intérêt et a dit oui je veux activer.", status="completed")
    assert result["qualification"] == "Prospect chaud"


def test_empty_transcript_and_summary_does_not_crash():
    result = provider.classify(transcript="", summary="", status="completed")
    assert result["qualification"] in ("Prospect tiède", "Pas intéressé", "Prospect chaud")


def test_real_call_via_webhook_uses_keyword_provider_not_random(client, db_session):
    """
    Test d'intégration : un vrai appel avec un transcript contenant un
    signal net doit être classifié de façon cohérente et répétable — pas
    aléatoire — en passant par le vrai chemin webhook.
    """
    from tests.conftest import auth_headers, register_user
    from app.models.agent import Agent
    from app.models.call import Call
    import uuid as uuid_module

    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}
    agent = client.post("/agents", json={"name": "Agent test"}, headers=headers).json()

    db_agent = db_session.query(Agent).filter(Agent.id == uuid_module.UUID(agent["id"])).first()
    db_agent.retell_agent_id = "retell_agent_keyword_test"
    db_session.commit()

    for i in range(3):
        db_session.add(Call(
            organization_id=uuid_module.UUID(org_id), agent_id=uuid_module.UUID(agent["id"]),
            direction="inbound", status="in_progress", provider="retell",
            provider_call_id=f"call_keyword_test_{i}",
        ))
    db_session.commit()

    # Même signal positif net envoyé 3 fois -> doit TOUJOURS donner le même résultat (déterministe)
    results = []
    for i in range(3):
        client.post("/webhooks/retell", json={
            "event": "call_analyzed",
            "call": {
                "call_id": f"call_keyword_test_{i}",
                "transcript": "Client: Oui je suis prêt, ça m'intéresse, je confirme.",
                "call_analysis": {"call_summary": "Client intéressé."},
            },
        })
        calls = client.get("/calls", headers=headers).json()
        matching = next(c for c in calls if c["provider_call_id"] == f"call_keyword_test_{i}")
        results.append(matching["qualification"])

    assert len(set(results)) == 1  # toujours le même résultat, jamais aléatoire
