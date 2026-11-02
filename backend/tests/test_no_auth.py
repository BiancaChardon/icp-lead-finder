from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.config import Settings
from app.deps import SHARED_USER_EMAIL
from app.main import create_app
from app.models import User
from tests.conftest import TABLES

ICP = {"criteria": {"industry": "Healthcare", "locations": ["Maryland"]}, "per_page": 10}


@pytest.fixture
def open_app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings.model_copy(update={"auth_required": False}))
    yield application
    with application.state.engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    application.state.engine.dispose()


@pytest.fixture
def open_client(open_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(open_app) as client:
        yield client


def test_auth_is_off_by_default():
    assert Settings(database_url="postgresql+psycopg://u:p@h/d").auth_required is False


def test_no_sign_in_needed(open_client: TestClient):
    me = open_client.get("/api/auth/me").json()
    assert me["auth_required"] is False
    assert me["user"]["email"] == SHARED_USER_EMAIL

    search = open_client.post("/api/search", json=ICP)
    assert search.status_code == 200 and search.json()["results"]

    lead = search.json()["results"][0]
    assert open_client.post("/api/leads", json={"leads": [lead]}).json() == {"saved": 1, "already_saved": 0}
    assert open_client.get("/api/leads").json()["total"] == 1
    assert open_client.get("/api/history").json()["total"] == 1
    assert open_client.get("/api/leads/export.csv").status_code == 200


def test_visitors_share_one_workspace(open_app: FastAPI, open_client: TestClient):
    search = open_client.post("/api/search", json=ICP).json()
    open_client.post("/api/leads", json={"leads": search["results"][:2]})

    with TestClient(open_app) as other_visitor:
        assert other_visitor.get("/api/leads").json()["total"] == 2

    with open_app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_untrusted_origin_still_rejected(open_client: TestClient):
    response = open_client.post("/api/search", json=ICP, headers={"Origin": "https://evil.example"})

    assert response.status_code == 403


def test_admin_features_unavailable(open_client: TestClient):
    assert open_client.get("/api/users").status_code == 403
    response = open_client.post(
        "/api/auth/change-password", json={"current_password": "x", "new_password": "long-enough-password"}
    )
    assert response.status_code == 400


def test_shared_workspace_cannot_be_signed_in_to(open_client: TestClient):
    open_client.get("/api/auth/me")

    response = open_client.post("/api/auth/login", json={"email": SHARED_USER_EMAIL, "password": "anything-at-all"})

    assert response.status_code in (401, 422)
    assert "csrf_token" not in response.text
