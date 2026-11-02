from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.config import Settings
from app.db import get_db
from app.deps import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    CurrentSession,
    get_current_session,
    get_settings_dep,
)
from app.models import AuthSession, User
from app.rate_limit import client_ip, enforce_rate_limit
from app.schemas import ChangePasswordRequest, LoginRequest, SessionOut, UserOut
from app.security import (
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID_LOGIN = "Invalid email or password"


def _set_auth_cookies(response: Response, settings: Settings, token: str, csrf: str) -> None:
    max_age = settings.session_ttl_hours * 3600
    common = {"max_age": max_age, "secure": settings.cookie_secure, "samesite": "lax", "path": "/"}
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **common)
    # Readable by the frontend so it can echo it back in the X-CSRF-Token header.
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="lax")


@router.post("/login", response_model=SessionOut)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> SessionOut:
    email = body.email.lower()
    limit = settings.login_rate_limit_per_minute
    enforce_rate_limit(request, f"login:ip:{client_ip(request)}", limit * 4)
    enforce_rate_limit(request, f"login:email:{email}", limit)

    user = db.scalar(select(User).where(User.email == email))
    password_ok = verify_password(user.password_hash if user else None, body.password)

    if user is None or not password_ok or not user.is_active:
        record_event(
            db,
            "login_failed",
            actor_user_id=user.id if user else None,
            details={"reason": "inactive" if (user and password_ok) else "invalid_credentials"},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_LOGIN)

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    now = datetime.now(UTC)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at <= now))
    token, csrf = new_token(), new_token()
    db.add(
        AuthSession(
            token_hash=hash_token(token),
            csrf_token=csrf,
            user_id=user.id,
            expires_at=now + timedelta(hours=settings.session_ttl_hours),
        )
    )
    user.last_login_at = now
    record_event(db, "login_succeeded", actor_user_id=user.id)
    db.commit()

    _set_auth_cookies(response, settings, token, csrf)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current: CurrentSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    db.delete(current.session)
    record_event(db, "logout", actor_user_id=current.user.id)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(response, settings)
    return response


@router.get("/me", response_model=SessionOut)
def me(current: CurrentSession = Depends(get_current_session)) -> SessionOut:
    return SessionOut(user=UserOut.model_validate(current.user), csrf_token=current.session.csrf_token)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current: CurrentSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    user = current.user
    enforce_rate_limit(request, f"change-password:{user.id}", settings.login_rate_limit_per_minute)
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.password_hash = hash_password(body.new_password)
    db.execute(
        delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != current.session.id)
    )
    record_event(db, "password_changed", actor_user_id=user.id, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
