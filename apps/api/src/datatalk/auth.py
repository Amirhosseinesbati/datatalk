import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_session
from .models import LoginSession, User

SESSION_COOKIE = "datatalk_session"
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(hash_value: str, password: str) -> bool:
    try:
        return password_hasher.verify(hash_value, password)
    except (VerifyMismatchError, ValueError):
        return False


def create_login_session(db: Session, user: User, response: Response) -> None:
    settings = get_settings()
    token = secrets.token_urlsafe(40)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(days=settings.datatalk_session_days)))
    db.commit()
    response.set_cookie(SESSION_COOKIE, token, max_age=settings.datatalk_session_days * 86400, httponly=True, secure=settings.datatalk_cookie_secure, samesite="lax", path="/")


def revoke_login_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        record = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
        if record:
            db.delete(record)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(request: Request, db: Session = Depends(get_session)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to access this workspace")
    record = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not record:
        raise HTTPException(status_code=401, detail="Session has expired")
    expiry = record.expires_at.replace(tzinfo=timezone.utc) if record.expires_at.tzinfo is None else record.expires_at
    if expiry <= datetime.now(timezone.utc):
        db.delete(record)
        db.commit()
        raise HTTPException(status_code=401, detail="Session has expired")
    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    return user


def require_role(*allowed: str):
    def _dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Your workspace role cannot perform this action")
        return user
    return _dependency


def public_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role, "workspace_id": user.workspace_id}
