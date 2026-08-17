"""
Fixtures pytest : base SQLite isolée en mémoire pour chaque run de tests,
indépendante de tout serveur Postgres réel (section 40 : tests sans coût).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture()
def db_session():
    # StaticPool : garde une seule connexion partagée, indispensable pour que
    # la base SQLite en mémoire soit visible par toutes les requêtes du test.
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------- Aides d'authentification, réutilisées par tous les tests ----------

import uuid  # noqa: E402


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_user(client, email: str | None = None, org_name: str = "Entreprise Test", password: str = "password123"):
    """Inscrit un nouvel utilisateur + son organisation, retourne (token, organization_id)."""
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Utilisateur Test",
            "organization_name": org_name,
        },
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    me = client.get("/auth/me", headers=auth_headers(token)).json()
    org_id = me["memberships"][0]["organization_id"]
    return token, org_id


def create_super_admin(client, email: str | None = None, password: str = "password123"):
    """Crée le Super Admin (une seule fois par base de test) et retourne son token."""
    email = email or f"admin-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/auth/bootstrap-super-admin",
        json={"email": email, "password": password, "full_name": "Super Admin"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
