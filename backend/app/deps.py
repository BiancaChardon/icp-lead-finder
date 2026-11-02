import hmac
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.models import AuthSession, User
from app.security import hash_password, hash_token, new_token

SESSION_COOKIE = "ilf_session"
CSRF_COOKIE = "ilf_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

SHARED_USER_EMAIL = "workspace@icp-lead-finder.local"


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


@dataclass
class CurrentSession:
    user: User
    session: AuthSession | None


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def get_shared_user(db: Session) -> User:
    """The single workspace user used by everyone when AUTH_REQUIRED is false."""
    user = db.scalar(select(User).where(User.email == SHARED_USER_EMAIL))
    if user is not None:
        return user
    user = User(
        email=SHARED_USER_EMAIL,
        full_name="Shared workspace",
        password_hash=hash_password(new_token()),  # random; the account cannot be signed in to
        role="member",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        user = db.scalar(select(User).where(User.email == SHARED_USER_EMAIL))
        assert user is not None
    return user


def get_current_session(request: Request, db: Session = Depends(get_db)) -> CurrentSession:
    settings: Settings = request.app.state.settings
    if not settings.auth_required:
        return CurrentSession(user=get_shared_user(db), session=None)

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise _unauthorized()

    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if auth_session is None or auth_session.expires_at <= datetime.now(UTC):
        raise _unauthorized()
    user = auth_session.user
    if not user.is_active:
        raise _unauthorized()

    if request.method not in SAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not supplied or not hmac.compare_digest(supplied, auth_session.csrf_token):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")

    return CurrentSession(user=user, session=auth_session)


def get_current_user(current: CurrentSession = Depends(get_current_session)) -> User:
    return current.user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user
