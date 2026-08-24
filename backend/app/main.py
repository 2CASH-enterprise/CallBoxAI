"""
Point d'entrée FastAPI.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.api.routes import health, organizations, agents, calls, contacts, distributors, auth, admin, campaigns, knowledge, analytics, webhooks, appointments, messages, surveys, tickets, pms, sms, dashboard_today, telecom

# Sans cette configuration explicite, les logger.info()/warning() de notre
# propre code (voir app.api.routes.webhooks, app.api.routes.pms,
# app.api.routes.agents...) sont SILENCIEUSEMENT IGNORÉS — seuls les
# journaux d'accès automatiques d'uvicorn (les lignes "POST ... 200 OK")
# apparaissent par défaut. Bug réel découvert lors du débogage en conditions
# réelles : plusieurs journaux de diagnostic ajoutés n'ont jamais été
# visibles avant cette correction.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Création des tables au démarrage (dev/tests uniquement ; en prod : migrations Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Contact Center Platform", version="0.1.0")

# CORS : nécessaire pour que le Dashboard client (Next.js, autre port/domaine)
# puisse appeler cette API depuis le navigateur.
# MVP : ouvert à tous les domaines. À restreindre à la liste des domaines du
# Dashboard client lors du passage en production (section 24 du cahier des charges).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(organizations.router)
app.include_router(agents.router)
app.include_router(calls.router)
app.include_router(contacts.router)
app.include_router(distributors.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(campaigns.router)
app.include_router(knowledge.router)
app.include_router(analytics.router)
app.include_router(webhooks.router)
app.include_router(appointments.router)
app.include_router(messages.router)
app.include_router(surveys.router)
app.include_router(tickets.router)
app.include_router(pms.router)
app.include_router(sms.router)
app.include_router(dashboard_today.router)
app.include_router(telecom.router)
