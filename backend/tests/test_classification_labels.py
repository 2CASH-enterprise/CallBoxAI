"""
Tests du vocabulaire de classification adapté au métier de l'agent
(section 19/41 du cahier des charges) — "Prospect tiède" n'a aucun sens
pour un client d'hôtel.
"""
from tests.conftest import auth_headers, register_user


def setup_org(client):
    token, org_id = register_user(client)
    return {**auth_headers(token), "x-organization-id": org_id}


def create_agent(client, headers, category, **overrides):
    payload = {"name": f"Agent {category}", "category": category}
    payload.update(overrides)
    return client.post("/agents", json=payload, headers=headers).json()


def test_agent_stores_category(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, "hotellerie")
    assert agent["category"] == "hotellerie"


def test_default_category_is_generique(client):
    headers = setup_org(client)
    agent = client.post("/agents", json={"name": "Agent sans catégorie"}, headers=headers).json()
    assert agent["category"] == "generique"


def test_hotellerie_calls_never_show_sales_vocabulary(client):
    """Test central : jamais 'Prospect chaud/tiède' pour un agent hôtelier."""
    headers = setup_org(client)
    agent = create_agent(client, headers, "hotellerie")

    sales_words = {"Prospect chaud", "Prospect tiède", "Pas intéressé"}
    seen_qualifications = set()
    for _ in range(40):
        call = client.post(
            "/calls", json={"agent_id": agent["id"], "to_number": "+33612340000", "from_number": "+33780000000"}, headers=headers
        ).json()
        seen_qualifications.add(call["qualification"])

    assert not (seen_qualifications & sales_words), f"Vocabulaire commercial trouvé : {seen_qualifications & sales_words}"
    assert "Client satisfait" in seen_qualifications or "Client à suivre" in seen_qualifications or "Client insatisfait" in seen_qualifications


def test_generique_and_prospection_keep_original_vocabulary(client):
    """Pas de régression : les catégories non traduites gardent le vocabulaire canonique."""
    headers = setup_org(client)
    agent = create_agent(client, headers, "prospection")

    seen_qualifications = set()
    for _ in range(30):
        call = client.post(
            "/calls", json={"agent_id": agent["id"], "to_number": "+33612340001", "from_number": "+33780000000"}, headers=headers
        ).json()
        seen_qualifications.add(call["qualification"])

    assert seen_qualifications <= {"Prospect chaud", "Prospect tiède", "Pas intéressé", "À suivre par un humain"}


def test_business_logic_unaffected_by_category_translation(client):
    """
    Point critique : même si l'étiquette affichée change, le CRM/la prise
    de rendez-vous doivent continuer à fonctionner identiquement pour un
    agent hôtelier que pour un agent générique.
    """
    headers = setup_org(client)
    agent = create_agent(client, headers, "hotellerie")
    contact = client.post("/contacts", json={"phone": "+33612340002"}, headers=headers).json()

    found_rdv = False
    for _ in range(60):
        client.post(
            "/calls",
            json={"agent_id": agent["id"], "to_number": "+33612340002", "from_number": "+33780000000", "contact_id": contact["id"]},
            headers=headers,
        )
        updated = client.get("/contacts", headers=headers).json()[0]
        if updated["status"] == "RDV":
            found_rdv = True
            break

    assert found_rdv, "Le statut CRM RDV doit toujours pouvoir être atteint, quelle que soit la catégorie"
    # Un vrai rendez-vous daté doit aussi avoir été créé (pas juste le statut)
    appointments = client.get("/appointments", headers=headers).json()
    assert len(appointments) >= 1


def test_ticket_category_uses_localized_intent(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, "hotellerie", ticketing_enabled=True)

    for _ in range(10):
        client.post(
            "/calls",
            json={"agent_id": agent["id"], "to_number": "+33612340003", "from_number": "+33780000000", "direction": "inbound"},
            headers=headers,
        )

    tickets = client.get("/tickets", headers=headers).json()
    assert len(tickets) == 10
    sales_categories = {"Demande de prix", "Prise de rendez-vous"}
    ticket_categories = {t["category"] for t in tickets}
    assert not (ticket_categories & sales_categories)


def test_service_client_category_translates_qualification(client):
    headers = setup_org(client)
    agent = create_agent(client, headers, "service_client")

    seen = set()
    for _ in range(30):
        call = client.post(
            "/calls", json={"agent_id": agent["id"], "to_number": "+33612340004", "from_number": "+33780000000"}, headers=headers
        ).json()
        seen.add(call["qualification"])

    assert "Prospect chaud" not in seen and "Prospect tiède" not in seen
    assert seen <= {"Résolu", "En cours de résolution", "Non résolu", "À suivre par un humain"}
