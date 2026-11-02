from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SavedLead
from tests.conftest import login


def demo_results(client: TestClient, count: int = 3) -> list[dict]:
    response = client.post("/api/search", json={"criteria": {"industry": "Healthcare"}, "per_page": 10})
    return response.json()["results"][:count]


def test_save_list_and_delete_leads(member_client: TestClient, db: Session):
    leads = demo_results(member_client)

    saved = member_client.post("/api/leads", json={"leads": leads})
    assert saved.json() == {"saved": 3, "already_saved": 0}

    again = member_client.post("/api/leads", json={"leads": leads[:2]})
    assert again.json() == {"saved": 0, "already_saved": 2}

    listing = member_client.get("/api/leads").json()
    assert listing["total"] == 3
    assert {item["provider_record_id"] for item in listing["items"]} == {l["provider_record_id"] for l in leads}
    assert all(item["is_demo"] for item in listing["items"])

    lead_id = listing["items"][0]["id"]
    assert member_client.delete(f"/api/leads/{lead_id}").status_code == 204
    assert member_client.get("/api/leads").json()["total"] == 2
    assert db.scalar(select(SavedLead).where(SavedLead.id == lead_id)) is None


def test_saved_leads_are_private(member_client: TestClient, app: FastAPI, make_user):
    member_client.post("/api/leads", json={"leads": demo_results(member_client, 1)})
    lead_id = member_client.get("/api/leads").json()["items"][0]["id"]
    make_user(email="other@example.com")

    with TestClient(app) as other:
        login(other, "other@example.com")
        assert other.get("/api/leads").json()["total"] == 0
        assert other.delete(f"/api/leads/{lead_id}").status_code == 404
        export = other.get("/api/leads/export.csv")
        assert export.status_code == 200
        assert len(export.text.strip().splitlines()) == 1, "only the header row"

    assert member_client.get("/api/leads").json()["total"] == 1


def test_unauthenticated_access_to_saved_leads_is_refused(client: TestClient):
    assert client.get("/api/leads").status_code == 401
    assert client.get("/api/leads/export.csv").status_code == 401
    assert client.delete("/api/leads/1").status_code == 401


def test_save_requires_csrf_token(member_client: TestClient):
    leads = demo_results(member_client, 1)
    del member_client.headers["X-CSRF-Token"]

    assert member_client.post("/api/leads", json={"leads": leads}).status_code == 403


def test_save_validates_lead_payload(member_client: TestClient):
    lead = demo_results(member_client, 1)[0]

    assert member_client.post("/api/leads", json={"leads": []}).status_code == 422
    assert member_client.post("/api/leads", json={"leads": [{**lead, "email_status": "trusted"}]}).status_code == 422
    assert member_client.post("/api/leads", json={"leads": [{**lead, "company_name": "x" * 500}]}).status_code == 422


def test_export_saved_leads_csv(member_client: TestClient):
    member_client.post("/api/leads", json={"leads": demo_results(member_client, 2)})

    response = member_client.get("/api/leads/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="saved-leads-' in response.headers["content-disposition"]
    lines = response.text.lstrip("\ufeff").strip().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith('"Company","First Name"')
