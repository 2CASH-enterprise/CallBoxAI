"""
Point d'entrée FastAPI.
"""
from fastapi import FastAPI

from app.core.database import Base, engine
from app.api.routes import health, organizations, agents, calls

# Création des tables au démarrage (dev/tests uniquement ; en prod : migrations Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Contact Center Platform", version="0.1.0")

app.include_router(health.router)
app.include_router(organizations.router)
app.include_router(agents.router)
app.include_router(calls.router)
