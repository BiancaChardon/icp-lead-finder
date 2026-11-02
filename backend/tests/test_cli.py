import io

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.models import AuditEvent, User


@pytest.fixture
def cli_env(monkeypatch, settings):
    monkeypatch.setattr(cli, "get_settings", lambda: settings)


def run_cli(monkeypatch, args: list[str], password: str) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(password + "\n"))
    return cli.main([*args, "--password-stdin"])


def test_create_admin(cli_env, monkeypatch, db: Session, capsys):
    code = run_cli(
        monkeypatch, ["create-admin", "--email", "Boss@Example.com", "--name", "The Boss"], "a-very-long-password"
    )

    assert code == 0
    user = db.scalar(select(User).where(User.email == "boss@example.com"))
    assert user is not None and user.role == "admin" and user.is_active
    assert user.password_hash.startswith("$argon2id$")
    assert "a-very-long-password" not in capsys.readouterr().out
    assert db.scalar(select(AuditEvent.event_type)) == "admin_created_via_cli"


def test_create_admin_rejects_duplicates_and_weak_passwords(cli_env, monkeypatch, make_user, capsys):
    make_user(email="taken@example.com")

    assert run_cli(monkeypatch, ["create-admin", "--email", "taken@example.com", "--name", "X"], "long-enough-pw") == 1
    assert run_cli(monkeypatch, ["create-admin", "--email", "new@example.com", "--name", "X"], "short") == 1
    assert run_cli(monkeypatch, ["create-admin", "--email", "not-an-email", "--name", "X"], "long-enough-pw") == 1
    assert "Error:" in capsys.readouterr().err


def test_reset_password(cli_env, monkeypatch, make_user, db: Session):
    user = make_user(email="locked@example.com", is_active=False)
    old_hash = user.password_hash

    assert run_cli(monkeypatch, ["reset-password", "--email", "locked@example.com"], "brand-new-password") == 0

    db.expire_all()
    refreshed = db.get(User, user.id)
    assert refreshed.password_hash != old_hash and refreshed.is_active
