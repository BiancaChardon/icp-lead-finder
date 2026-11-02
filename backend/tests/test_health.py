import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def make_client(**settings_kwargs) -> TestClient:
    return TestClient(create_app(Settings(**settings_kwargs)))


def test_health_returns_ok():
    response = make_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "backend"}


def test_health_does_not_disclose_configuration():
    client = make_client(cors_allowed_origins="http://localhost:3000")

    body = client.get("/health").text.lower()

    for sensitive in ("password", "secret", "key", "token", "postgres", "localhost", "development"):
        assert sensitive not in body


def test_cors_allows_configured_origin():
    client = make_client(cors_allowed_origins="http://localhost:3000")

    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unlisted_origin():
    client = make_client(cors_allowed_origins="http://localhost:3000")

    response = client.get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_wildcard_cors_rejected_in_production():
    with pytest.raises(ValidationError):
        Settings(app_env="production", cors_allowed_origins="*")


def test_docs_disabled_in_production():
    client = make_client(app_env="production", cors_allowed_origins="https://app.example")

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
