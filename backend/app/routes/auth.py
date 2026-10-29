from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import JWT_EXPIRE_MINUTES
from ..database import get_db
from ..models import User
from ..schemas import LoginIn, TokenOut, UserOut
from ..security import create_token, get_current_user, hash_password, verify_password
from ..services import audit

router = APIRouter(prefix="/auth", tags=["auth"])
# Used so a login for an unknown username takes about as long as a wrong password.
DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    password_ok = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok or not user.is_active:
        audit(db, "LOGIN", "FAILURE", user, detail="invalid credentials or inactive account",
              username=data.username)
        raise HTTPException(401, "Invalid username or password")
    audit(db, "LOGIN", "SUCCESS", user)
    return TokenOut(access_token=create_token(user), expires_in=JWT_EXPIRE_MINUTES * 60, user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Bumping the version makes every token issued so far for this user invalid.
    user.token_version += 1
    db.commit()
    audit(db, "LOGOUT", "SUCCESS", user)
