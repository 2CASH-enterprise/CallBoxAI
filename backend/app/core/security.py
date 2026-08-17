"""
Authentification et autorisation (section 24 du cahier des charges).

Remplace la confiance aveugle dans le header x-organization-id des premières
versions : désormais, chaque route vérifie que l'utilisateur connecté (via
un token JWT) a réellement le droit d'accéder à la ressource demandée.
"""
import uuid
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.organization_membership import OrganizationMembership

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 jours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session invalide ou expirée, merci de vous reconnecter.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_error
    except jwt.PyJWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise credentials_error
    return user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Réservé au Super Admin")
    return current_user


def require_organization_access(
    x_organization_id: str = Header(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    """
    Vérifie que l'utilisateur connecté est bien membre de cette organisation
    (ou Super Admin) avant de laisser passer la requête.
    """
    try:
        org_id = uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="x-organization-id invalide")

    if current_user.is_super_admin:
        return org_id

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.organization_id == org_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Accès refusé à cette organisation")
    return org_id


def require_distributor_access(
    distributor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> uuid.UUID:
    """
    Un Distributeur ne peut accéder qu'à SON propre portefeuille ; le Super
    Admin peut accéder à tous (section 39.4 du cahier des charges).
    """
    if current_user.is_super_admin:
        return distributor_id
    if current_user.distributor_id == distributor_id:
        return distributor_id
    raise HTTPException(status_code=403, detail="Accès refusé à ce portefeuille distributeur")
