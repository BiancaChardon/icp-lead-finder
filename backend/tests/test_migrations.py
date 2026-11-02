import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db import Base
from tests.conftest import alembic_config

EXPECTED_TABLES = {"users", "auth_sessions", "search_history", "saved_leads", "audit_events"}


@pytest.fixture
def engine(database_url: str):
    eng = create_engine(database_url)
    yield eng
    with eng.begin() as conn:
        conn.execute(text("TRUNCATE users, auth_sessions, search_history, saved_leads, audit_events CASCADE"))
    eng.dispose()


def test_migrations_match_models(engine):
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)

    assert diff == [], f"models and migrations differ: {diff}"


def test_downgrade_and_upgrade_round_trip(database_url: str, engine):
    cfg = alembic_config(database_url)

    command.downgrade(cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(inspect(engine).get_table_names())

    command.upgrade(cfg, "head")
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_indexes_present(engine):
    inspector = inspect(engine)

    assert "ix_search_history_user_id_created_at" in {i["name"] for i in inspector.get_indexes("search_history")}
    assert "ix_saved_leads_user_id_created_at" in {i["name"] for i in inspector.get_indexes("saved_leads")}
    assert "ix_audit_events_event_type" in {i["name"] for i in inspector.get_indexes("audit_events")}


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO users (email, full_name, password_hash, role) VALUES ('UPPER@example.com', 'x', 'h', 'member')",
        "INSERT INTO users (email, full_name, password_hash, role) VALUES ('a@example.com', 'x', 'h', 'superuser')",
    ],
)
def test_user_constraints(engine, sql):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(sql))


def test_duplicate_email_rejected(engine):
    insert = "INSERT INTO users (email, full_name, password_hash) VALUES ('dup@example.com', 'x', 'h')"
    with engine.begin() as conn:
        conn.execute(text(insert))
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(insert))


def test_saved_lead_constraints(engine):
    with engine.begin() as conn:
        user_id = conn.execute(
            text("INSERT INTO users (email, full_name, password_hash) VALUES ('l@example.com', 'x', 'h') RETURNING id")
        ).scalar_one()

    lead = (
        "INSERT INTO saved_leads (user_id, provider, provider_record_id, is_demo, email_status, phone_status, "
        "data_source) VALUES (:uid, 'mock', 'demo-1', true, :status, 'unavailable', 'Demo')"
    )
    with engine.begin() as conn:
        conn.execute(text(lead), {"uid": user_id, "status": "verified"})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(lead), {"uid": user_id, "status": "verified"})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(lead.replace("demo-1", "demo-2")), {"uid": user_id, "status": "made-up"})

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        remaining = conn.execute(text("SELECT count(*) FROM saved_leads")).scalar_one()
    assert remaining == 0, "saved leads are deleted with their owner"
