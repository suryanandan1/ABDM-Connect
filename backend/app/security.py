"""Password hashing, JWT tokens and the 'who is logged in' dependencies."""
from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import JWT_EXPIRE_MINUTES, JWT_SECRET
from .database import get_db, utcnow
from .models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "ver": user.token_version,
        "exp": utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    error = HTTPException(401, "Not authenticated or session expired", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise error
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise error
    user = db.get(User, int(payload["sub"]))
    # The role, facility and patient link always come from the database, never from the client.
    if user is None or not user.is_active or payload.get("ver") != user.token_version:
        raise error
    return user


def require_roles(*roles):
    """Use as Depends(require_roles("LAB")) to allow only some roles."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Your role is not allowed to do this")
        return user

    return checker
