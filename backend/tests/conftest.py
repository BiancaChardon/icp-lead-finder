import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import CSRF_HEADER
from app.main import create_app
from app.models import User
from app.security import hash_password

TEST_ORIGIN = "http://localhost:3000"
PASSWORD = "correct-horse-battery-staple"
TABLES = "users, auth_sessions, search_history, saved_leads, audit_events"
ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def alembic_config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session")
def database_url() -> str:
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database and url.database.endswith("_test"), "TEST_DATABASE_URL must name a *_test database"

    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()

    rendered = url.render_as_string(hide_password=False)
    command.upgrade(alembic_config(rendered), "head")
    return rendered


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(database_url=database_url, cors_allowed_origins=TEST_ORIGIN, contact_provider="mock")


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    yield application
    with application.state.engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    session = app.state.session_factory()
    yield session
    session.close()


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _make(
        email: str = "member@example.com",
        password: str = PASSWORD,
        role: str = "member",
        is_active: bool = True,
        full_name: str = "Test User",
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        return user

    return _make


def login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    csrf = response.json()["csrf_token"]
    client.headers[CSRF_HEADER] = csrf
    return csrf


@pytest.fixture
def member_client(client: TestClient, make_user: Callable[..., User]) -> TestClient:
    make_user()
    login(client, "member@example.com")
    return client


@pytest.fixture
def admin_client(client: TestClient, make_user: Callable[..., User]) -> TestClient:
    make_user(email="admin@example.com", role="admin", full_name="Admin User")
    login(client, "admin@example.com")
    return client
