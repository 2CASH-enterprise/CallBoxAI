"""
Point d'entrée FastAPI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.api.routes import health, organizations, agents, calls, contacts, distributors, auth, admin, campaigns, knowledge, analytics

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
