from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.deps import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from app.models import AuditEvent, AuthSession, User
from app.security import hash_token
from tests.conftest import PASSWORD, login


def _events(db: Session) -> list[str]:
    db.expire_all()
    return list(db.scalars(select(AuditEvent.event_type).order_by(AuditEvent.id)))


def test_login_sets_secure_session_cookies(client: TestClient, make_user, db: Session):
    make_user()

    response = client.post("/api/auth/login", json={"email": "Member@Example.com", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "member@example.com"
    assert "password_hash" not in body["user"]
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith(f"{SESSION_COOKIE}="))
    csrf_cookie = next(c for c in cookies if c.startswith(f"{CSRF_COOKIE}="))
    assert "HttpOnly" in session_cookie
    assert "samesite=lax" in session_cookie.lower()
    assert "Max-Age=43200" in session_cookie
    assert "HttpOnly" not in csrf_cookie

    token = client.cookies.get(SESSION_COOKIE)
    stored = db.scalar(select(AuthSession))
    assert stored is not None and stored.token_hash == hash_token(token)
    assert token not in stored.token_hash
    assert "login_succeeded" in _events(db)


def test_cookies_marked_secure_when_configured(settings, make_user):
    from app.main import create_app

    app = create_app(settings.model_copy(update={"cookie_secure": True}))
    with TestClient(app) as client:
        make_user()
        response = client.post("/api/auth/login", json={"email": "member@example.com", "password": PASSWORD})
    assert all("Secure" in c for c in response.headers.get_list("set-cookie"))
    app.state.engine.dispose()


def test_passwords_are_hashed_with_argon2(make_user):
    user = make_user()

    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


def test_wrong_password_and_unknown_email_get_same_error(client: TestClient, make_user, db: Session):
    make_user()

    wrong = client.post("/api/auth/login", json={"email": "member@example.com", "password": "nope-nope-nope"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": PASSWORD})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password"}
    assert _events(db).count("login_failed") == 2


def test_inactive_user_cannot_log_in(client: TestClient, make_user):
    make_user(is_active=False)

    response = client.post("/api/auth/login", json={"email": "member@example.com", "password": PASSWORD})

    assert response.status_code == 401


def test_login_is_rate_limited(client: TestClient, make_user):
    make_user()
    statuses = [
        client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password!"}).status_code
        for _ in range(6)
    ]

    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


def test_protected_endpoints_require_login(client: TestClient):
    checks = [
        ("get", "/api/auth/me"),
        ("get", "/api/search/provider"),
        ("post", "/api/search"),
        ("post", "/api/export/csv"),
        ("get", "/api/leads"),
        ("post", "/api/leads"),
        ("get", "/api/leads/export.csv"),
        ("delete", "/api/leads/1"),
        ("get", "/api/history"),
        ("get", "/api/history/1"),
        ("get", "/api/users"),
        ("post", "/api/users"),
    ]
    for method, path in checks:
        response = client.request(method.upper(), path, json={} if method == "post" else None)
        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


def test_no_public_registration(client: TestClient):
    response = client.post(
        "/api/users",
        json={"email": "new@example.com", "full_name": "New", "password": "long-enough-password", "role": "admin"},
    )

    assert response.status_code == 401


def test_me_and_logout(member_client: TestClient, db: Session):
    me = member_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "member@example.com"

    logout = member_client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert db.scalar(select(AuthSession)) is None
    assert member_client.get("/api/auth/me").status_code == 401


def test_expired_session_is_rejected(member_client: TestClient, db: Session):
    db.execute(update(AuthSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    db.commit()

    assert member_client.get("/api/auth/me").status_code == 401


def test_state_changing_request_requires_csrf_token(member_client: TestClient):
    del member_client.headers[CSRF_HEADER]
    assert member_client.post("/api/auth/logout").status_code == 403

    member_client.headers[CSRF_HEADER] = "forged"
    assert member_client.post("/api/auth/logout").status_code == 403


def test_untrusted_origin_is_rejected(member_client: TestClient):
    response = member_client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert member_client.post("/api/auth/logout", headers={"Origin": "http://localhost:3000"}).status_code == 204


def test_change_password(member_client: TestClient, db: Session):
    bad = member_client.post(
        "/api/auth/change-password",
        json={"current_password": "not-my-password", "new_password": "a-brand-new-password"},
    )
    assert bad.status_code == 400

    short = member_client.post(
        "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"}
    )
    assert short.status_code == 422

    ok = member_client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert ok.status_code == 204
    member_client.post("/api/auth/logout")
    login(member_client, "member@example.com", "a-brand-new-password")
    assert "password_changed" in _events(db)


def test_member_cannot_manage_users(member_client: TestClient):
    assert member_client.get("/api/users").status_code == 403
    response = member_client.post(
        "/api/users",
        json={"email": "x@example.com", "full_name": "X", "password": "long-enough-password"},
    )
    assert response.status_code == 403


def test_admin_creates_and_deactivates_user(admin_client: TestClient, app: FastAPI, db: Session):
    created = admin_client.post(
        "/api/users",
        json={"email": "New.Person@Example.com", "full_name": "New Person", "password": "long-enough-password"},
    )
    assert created.status_code == 201
    new_user = created.json()
    assert new_user["email"] == "new.person@example.com"
    assert new_user["role"] == "member"

    duplicate = admin_client.post(
        "/api/users",
        json={"email": "new.person@example.com", "full_name": "Dup", "password": "long-enough-password"},
    )
    assert duplicate.status_code == 409

    with TestClient(app) as other:
        login(other, "new.person@example.com", "long-enough-password")
        deactivate = admin_client.patch(f"/api/users/{new_user['id']}", json={"is_active": False})
        assert deactivate.status_code == 200
        assert other.get("/api/auth/me").status_code == 401

    events = _events(db)
    assert "user_created" in events and "user_updated" in events


def test_admin_cannot_lock_themselves_out(admin_client: TestClient, db: Session):
    admin = db.scalar(select(User).where(User.email == "admin@example.com"))

    assert admin_client.patch(f"/api/users/{admin.id}", json={"is_active": False}).status_code == 400
    assert admin_client.patch(f"/api/users/{admin.id}", json={"role": "member"}).status_code == 400


def test_admin_resets_password(admin_client: TestClient, make_user, app: FastAPI):
    user = make_user(email="forgetful@example.com")

    response = admin_client.post(f"/api/users/{user.id}/password", json={"new_password": "reset-password-123"})

    assert response.status_code == 204
    with TestClient(app) as other:
        login(other, "forgetful@example.com", "reset-password-123")


def test_audit_details_never_contain_secrets(client: TestClient, make_user, db: Session):
    make_user()
    client.post("/api/auth/login", json={"email": "member@example.com", "password": "wrong-password!!"})
    login(client, "member@example.com")

    db.expire_all()
    for event in db.scalars(select(AuditEvent)):
        serialized = str(event.details)
        assert PASSWORD not in serialized and "wrong-password" not in serialized
