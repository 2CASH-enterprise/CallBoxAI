# Plateforme SaaS d'Agents IA vocaux — Afrique francophone

Ce dépôt suit la stratégie de développement à coût zéro décrite dans le cahier des
charges (section 40) : tout fonctionne en local avec des providers **Mock**
(téléphonie, voix IA, messagerie, KYC), sans compte Twilio/Retell/eKYC payant.

## Démarrage rapide (local, sans Docker)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate      # sous Windows : .venv\Scripts\activate
pip install -r requirements.txt

# Lancer les tests
PYTHONPATH=. pytest tests/ -v

# Lancer le serveur de développement
uvicorn app.main:app --reload
```

L'API est alors disponible sur http://localhost:8000, documentation interactive
sur http://localhost:8000/docs.

## Démarrage avec Docker (Postgres, Redis, MinIO, Mailhog inclus)

```bash
docker compose up --build
```

## Tester l'API manuellement

```bash
# Créer une entreprise
curl -X POST http://localhost:8000/organizations \
  -H "Content-Type: application/json" \
  -d '{"name": "Entreprise Test", "country": "SN"}'

# Créer un agent (remplacer ORG_ID par l'id reçu ci-dessus)
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -H "x-organization-id: ORG_ID" \
  -d '{"name": "Agent commercial", "system_prompt": "Tu es un agent commercial."}'

# Passer un appel simulé (remplacer AGENT_ID)
curl -X POST http://localhost:8000/calls \
  -H "Content-Type: application/json" \
  -H "x-organization-id: ORG_ID" \
  -d '{"agent_id": "AGENT_ID", "to_number": "+221770000000", "from_number": "+221780000000"}'
```

## Structure du projet

```
backend/
  app/
    core/         configuration, connexion base de données
    models/        organizations, distributors, agents, contacts, calls, kyc
    providers/      interfaces abstraites + implémentations Mock (section 5)
    api/routes/     endpoints REST
  tests/            tests automatisés (pytest)
frontend/          (à venir)
docker-compose.yml  environnement local complet
```

## Principes à respecter (rappel du cahier des charges)

- **Isolation multi-tenant stricte** : toute donnée est rattachée à un `organization_id` (voir `test_multi_tenant_isolation.py`).
- **Abstraction des fournisseurs** : jamais d'appel direct à Twilio/Retell/WhatsApp/eKYC dans la logique métier — toujours passer par une interface `Provider` (section 5).
- **Aucun secret fournisseur dans le code ou le frontend** — toujours via variables d'environnement.
