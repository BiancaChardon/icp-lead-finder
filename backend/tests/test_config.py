import pytest
from pydantic import ValidationError

from app.config import Settings

DB = "postgresql+psycopg://user:pass@db:5432/app"
PROD_OK = {
    "database_url": DB,
    "app_env": "production",
    "cors_allowed_origins": "https://leads.example.com",
    "cookie_secure": True,
    "contact_provider": "mock",
}


def test_valid_production_configuration():
    settings = Settings(**PROD_OK)

    assert settings.is_production
    assert settings.cors_origin_list == ["https://leads.example.com"]


@pytest.mark.parametrize(
    "override",
    [
        {"cors_allowed_origins": "*"},
        {"cors_allowed_origins": ""},
        {"cors_allowed_origins": "http://leads.example.com"},
        {"cookie_secure": False},
        {"contact_provider": ""},
    ],
)
def test_production_requires_explicit_secure_configuration(override):
    with pytest.raises(ValidationError):
        Settings(**{**PROD_OK, **override})


def test_wildcard_cors_rejected_in_development():
    with pytest.raises(ValidationError):
        Settings(database_url=DB, cors_allowed_origins="http://localhost:3000,*")


def test_development_defaults_to_mock_provider():
    settings = Settings(database_url=DB, contact_provider="  ")

    assert settings.contact_provider is None
    assert settings.resolved_contact_provider == "mock"


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]
