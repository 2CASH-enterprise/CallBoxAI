"""
Authentification (section 24) et création de compte en libre-service (section 6.1).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization_name: str
    organization_country: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class BootstrapSuperAdminRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
        return v


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    role: str


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_super_admin: bool
    distributor_id: uuid.UUID | None
    memberships: list[MembershipOut]


def _issue_token(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Inscription en libre-service : crée le compte utilisateur ET son
    entreprise en une fois, avec le rôle "owner" (section 6.1).
    """
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.flush()

    org = Organization(name=payload.organization_name, country=payload.organization_country)
    db.add(org)
    db.flush()

    db.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role="owner"))
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    return _issue_token(user)


@router.post("/bootstrap-super-admin", response_model=TokenOut)
def bootstrap_super_admin(payload: BootstrapSuperAdminRequest, db: Session = Depends(get_db)):
    """
    Crée le tout premier compte Super Admin de la plateforme. Ne fonctionne
    que s'il n'en existe encore aucun — évite le problème de l'oeuf et la
    poule au tout premier déploiement, sans laisser un accès permanent non
    protégé pour créer des admins.
    """
    existing_admin = db.query(User).filter(User.is_super_admin.is_(True)).first()
    if existing_admin:
        raise HTTPException(status_code=403, detail="Un Super Admin existe déjà sur cette plateforme")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        is_super_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.get("/me", response_model=MeOut)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .filter(OrganizationMembership.user_id == current_user.id)
        .all()
    )
    return MeOut(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_super_admin=current_user.is_super_admin,
        distributor_id=current_user.distributor_id,
        memberships=[
            MembershipOut(organization_id=org.id, organization_name=org.name, role=m.role)
            for m, org in rows
        ],
    )
