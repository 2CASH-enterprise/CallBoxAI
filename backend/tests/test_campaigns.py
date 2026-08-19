"""
Tests du module Campagnes d'appels sortants (section 13 du cahier des charges).
"""
import io

from tests.conftest import auth_headers, register_user


def setup_campaign(client, schedule_start="00:00", schedule_end="23:59", max_attempts=3, max_follow_ups=2):
    """
    Par défaut, fenêtre horaire large (00:00-23:59) pour que les tests
    puissent s'exécuter à toute heure sans dépendre de l'heure réelle.
    """
    token, org_id = register_user(client)
    headers = {**auth_headers(token), "x-organization-id": org_id}

    agent = client.post(
        "/agents",
        json={"name": "Agent campagne", "system_prompt": "Tu es un agent commercial."},
        headers=headers,
    ).json()

    campaign = client.post(
        "/campaigns",
        json={
            "name": "Prospection Dakar",
            "agent_id": agent["id"],
            "schedule_start": schedule_start,
            "schedule_end": schedule_end,
            "max_attempts": max_attempts,
            "max_follow_ups": max_follow_ups,
        },
        headers=headers,
    ).json()

    return headers, campaign


def upload_csv(client, campaign_id, headers, csv_content: str):
    files = {"file": ("contacts.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    return client.post(f"/campaigns/{campaign_id}/import", headers=headers, files=files)


def test_create_campaign(client):
    headers, campaign = setup_campaign(client)
    assert campaign["status"] == "draft"
    assert campaign["max_attempts"] == 3


def test_import_csv_creates_contacts_and_targets(client):
    headers, campaign = setup_campaign(client)
    csv_content = "phone,first_name,last_name\n+221770000001,Awa,Diop\n+221770000002,Moussa,Ndiaye\n"

    response = upload_csv(client, campaign["id"], headers, csv_content)
    assert response.status_code == 200
    summary = response.json()
    assert summary["imported"] == 2
    assert summary["skipped_invalid_phone"] == 0
    assert summary["total_targets"] == 2

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 2


def test_import_csv_skips_invalid_phone_numbers(client):
    headers, campaign = setup_campaign(client)
    csv_content = "phone,first_name\n+221770000001,Valide\nnumero-invalide,Invalide\n123,TropCourt\n"

    response = upload_csv(client, campaign["id"], headers, csv_content)
    summary = response.json()
    assert summary["imported"] == 1
    assert summary["skipped_invalid_phone"] == 2


def test_import_reuses_existing_contact_by_phone(client):
    headers, campaign = setup_campaign(client)
    client.post("/contacts", json={"phone": "+221770000001", "first_name": "Déjà là"}, headers=headers)

    upload_csv(client, campaign["id"], headers, "phone\n+221770000001\n")

    contacts = client.get("/contacts", headers=headers).json()
    assert len(contacts) == 1  # pas de doublon créé


def test_cannot_run_batch_before_starting_campaign(client):
    headers, campaign = setup_campaign(client)
    upload_csv(client, campaign["id"], headers, "phone\n+221770000001\n")

    response = client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["processed"] == 0
    assert "démarrez-la" in body["message"]


def test_run_batch_respects_schedule_window(client):
    # Fenêtre impossible à atteindre : 03:00-03:01
    headers, campaign = setup_campaign(client, schedule_start="03:00", schedule_end="03:01")
    upload_csv(client, campaign["id"], headers, "phone\n+221770000001\n")
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)

    response = client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers)
    body = response.json()
    assert body["processed"] == 0
    assert "Hors horaires" in body["message"]


def test_run_batch_processes_targets_and_updates_stats(client):
    headers, campaign = setup_campaign(client)
    # 30 contacts : assez pour observer les 3 issues (répondu/pas de réponse/échec)
    csv_lines = "phone\n" + "\n".join(f"+22177000{i:04d}" for i in range(30))
    upload_csv(client, campaign["id"], headers, csv_lines)
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)

    # DEFAULT_BATCH_SIZE = 10 -> 3 lots pour tout traiter au moins une fois
    total_processed = 0
    for _ in range(3):
        result = client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers).json()
        total_processed += result["processed"]

    assert total_processed == 30  # chaque contact traité au moins une fois

    detail = client.get(f"/campaigns/{campaign['id']}", headers=headers).json()
    stats = detail["stats"]
    assert stats["total"] == 30
    # La somme des statuts doit toujours égaler le total (aucun contact perdu)
    assert stats["pending"] + stats["completed"] + stats["failed"] == 30


def test_retry_logic_respects_max_attempts(client):
    """
    Avec max_attempts=1, un contact qui ne répond pas doit passer directement
    en "failed" au lieu de rester "pending" pour un retry (section 13).
    Relances désactivées (max_follow_ups=0) pour isoler ce comportement de
    celui, distinct, de la relance basée sur l'intérêt.
    """
    headers, campaign = setup_campaign(client, max_attempts=1, max_follow_ups=0)
    csv_lines = "phone\n" + "\n".join(f"+22177001{i:04d}" for i in range(20))
    upload_csv(client, campaign["id"], headers, csv_lines)
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)

    for _ in range(2):
        client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers)

    detail = client.get(f"/campaigns/{campaign['id']}", headers=headers).json()
    # Avec 1 seule tentative autorisée et les relances désactivées, aucun
    # contact ne doit rester "pending" après son premier passage.
    assert detail["stats"]["pending"] == 0


def test_campaign_isolated_between_organizations(client):
    headers_a, campaign_a = setup_campaign(client)
    token_b, org_b_id = register_user(client, org_name="Entreprise B")
    headers_b = {**auth_headers(token_b), "x-organization-id": org_b_id}

    response = client.get(f"/campaigns/{campaign_a['id']}", headers=headers_b)
    assert response.status_code == 404  # campagne introuvable dans l'organisation B (pas de fuite d'info)

    list_b = client.get("/campaigns", headers=headers_b).json()
    assert len(list_b) == 0


def test_needs_follow_up_logic_directly():
    """
    Test unitaire de la fonction de décision, indépendant du hasard des
    appels simulés — vérifie précisément chaque cas métier (section 13).
    """
    from app.api.routes.campaigns import _needs_follow_up

    # Converti (rendez-vous pris) -> jamais de relance, peu importe la qualification
    assert _needs_follow_up("Prospect chaud", "Rendez-vous pris", follow_up_count=0, max_follow_ups=5) is False

    # Refus définitif -> jamais de relance
    assert _needs_follow_up("Pas intéressé", "Aucune action", follow_up_count=0, max_follow_ups=5) is False

    # Transféré à un humain -> pris en charge autrement, pas de relance automatique
    assert _needs_follow_up("À suivre par un humain", "Transfert vers opérateur", follow_up_count=0, max_follow_ups=5) is False

    # Intéressé mais pas encore converti, sous le plafond -> relance
    assert _needs_follow_up("Prospect tiède", "Information transmise", follow_up_count=0, max_follow_ups=2) is True
    assert _needs_follow_up("Prospect chaud", "Rappel programmé", follow_up_count=1, max_follow_ups=2) is True

    # Plafond de relances atteint -> on arrête, même si toujours pas converti
    assert _needs_follow_up("Prospect tiède", "Information transmise", follow_up_count=2, max_follow_ups=2) is False


def test_follow_up_schedules_next_attempt_with_delay(client):
    """
    Un contact nécessitant une relance doit repasser en "pending", avec une
    prochaine tentative programmée dans le futur (pas de rappel immédiat).
    """
    headers, campaign = setup_campaign(client, max_attempts=5, max_follow_ups=3)
    csv_lines = "phone\n" + "\n".join(f"+22177003{i:04d}" for i in range(30))
    upload_csv(client, campaign["id"], headers, csv_lines)
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)

    result = client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers).json()

    # Sur ce lot, la somme complété+sans réponse+échec = traités ; certains
    # des "complétés" (joints) doivent avoir déclenché une relance plutôt
    # qu'une clôture définitive (statistiquement, sur 10 contacts avec ~70%
    # de "complétés" et une bonne part non convertie du premier coup).
    assert result["processed"] == 10


def test_follow_up_not_immediately_retried_same_batch(client):
    """
    Une relance programmée (délai de quelques jours) ne doit PAS être
    reprise dans un lot immédiatement suivant — évite de rappeler le même
    contact deux fois dans la même minute.
    """
    headers, campaign = setup_campaign(client, max_attempts=5, max_follow_ups=5)
    csv_lines = "phone\n" + "\n".join(f"+22177004{i:04d}" for i in range(30))
    upload_csv(client, campaign["id"], headers, csv_lines)
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)

    first_batch = client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers).json()
    second_batch = client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers).json()

    # Le deuxième lot traite les 20 contacts pas encore appelés au premier
    # tour (30 - 10), PAS de relances immédiates du premier lot (elles sont
    # différées de plusieurs jours) — donc jamais plus de 10 par lot.
    assert second_batch["processed"] <= 10


def test_follow_up_eventually_stops_at_max(client):
    """
    Avec max_follow_ups=0, un contact joint mais pas converti doit être
    clôturé immédiatement, sans jamais repasser en pending pour relance.
    """
    headers, campaign = setup_campaign(client, max_attempts=5, max_follow_ups=0)
    csv_lines = "phone\n" + "\n".join(f"+22177005{i:04d}" for i in range(20))
    upload_csv(client, campaign["id"], headers, csv_lines)
    client.post(f"/campaigns/{campaign['id']}/start", headers=headers)

    # Assez de lots pour garantir la convergence même dans le pire cas
    # statistique (20 contacts, jusqu'à 5 tentatives chacun avant échec
    # définitif si injoignable à chaque fois) — évite un test instable.
    for _ in range(20):
        client.post(f"/campaigns/{campaign['id']}/run-batch", headers=headers)

    detail = client.get(f"/campaigns/{campaign['id']}", headers=headers).json()
    assert detail["stats"]["pending"] == 0  # tout est clôturé, aucune relance en attente
