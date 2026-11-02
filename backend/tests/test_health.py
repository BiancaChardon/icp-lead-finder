from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_ok(client: TestClient):
    for path in ("/health", "/api/health"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "backend"}


def test_health_does_not_disclose_configuration(client: TestClient):
    for path in ("/health", "/health/ready"):
        body = client.get(path).text.lower()
        for sensitive in ("password", "secret", "key", "token", "postgres", "localhost", "development", "mock"):
            assert sensitive not in body


def test_readiness_checks_database(client: TestClient):
    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_reports_database_outage_without_details():
    settings = Settings(database_url="postgresql+psycopg://nobody:hunter2@127.0.0.1:1/missing_db")
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    for leaked in ("hunter2", "127.0.0.1", "missing_db"):
        assert leaked not in response.text


def test_api_responses_have_security_headers(client: TestClient):
    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_cors_allows_configured_origin(client: TestClient):
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unlisted_origin(client: TestClient):
    response = client.get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_docs_disabled_in_production(database_url: str):
    settings = Settings(
        database_url=database_url,
        app_env="production",
        cors_allowed_origins="https://leads.example.com",
        cookie_secure=True,
        contact_provider="mock",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
