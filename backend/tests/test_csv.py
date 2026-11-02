import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.csv_export import COLUMNS, escape_cell, prospects_to_csv
from app.schemas import Prospect


def make_prospect(**overrides) -> Prospect:
    base = {
        "provider": "mock",
        "provider_record_id": "demo-0001",
        "is_demo": True,
        "data_source": "Demo data (mock provider)",
        "company_name": "Bluepine Health",
        "first_name": "Avery",
        "last_name": "Ashford",
        "job_title": "IT Director",
        "email": "avery.ashford@bluepine-health.example",
        "email_status": "verified",
        "phone": None,
        "employee_count": 250,
        "city": "Baltimore",
        "state": "MD",
        "country": "United States",
    }
    return Prospect(**{**base, **overrides})


def parse(text: str) -> list[list[str]]:
    assert text.startswith("\ufeff")
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


@pytest.mark.parametrize(
    "value,expected",
    [
        ("=HYPERLINK(\"http://evil\")", "'=HYPERLINK(\"http://evil\")"),
        ("+1 410-555-0100", "'+1 410-555-0100"),
        ("-2+3", "'-2+3"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tcmd", "'\tcmd"),
        ("\rcmd", "'\rcmd"),
        ("Normal Co", "Normal Co"),
        (None, ""),
        (True, "Yes"),
        (False, "No"),
        (250, "250"),
    ],
)
def test_escape_cell(value, expected):
    assert escape_cell(value) == expected


def test_csv_layout_and_unavailable_fields():
    rows = parse(prospects_to_csv([make_prospect()]))

    assert rows[0] == [header for header, _ in COLUMNS]
    row = dict(zip(rows[0], rows[1], strict=True))
    assert row["Company"] == "Bluepine Health"
    assert row["Email Status"] == "verified"
    assert row["Phone"] == "" and row["Phone Status"] == "unavailable"
    assert row["Demo Data"] == "Yes"


def test_csv_escapes_injected_values():
    rows = parse(prospects_to_csv([make_prospect(company_name="=cmd|' /C calc'!A0", last_name="@evil")]))

    row = dict(zip(rows[0], rows[1], strict=True))
    assert row["Company"].startswith("'=")
    assert row["Last Name"] == "'@evil"


def test_export_endpoint(member_client: TestClient):
    records = [make_prospect().model_dump(), make_prospect(provider_record_id="demo-0002", company_name="+evil").model_dump()]

    response = member_client.post("/api/export/csv", json={"records": records})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="icp-leads-' in response.headers["content-disposition"]
    rows = parse(response.text)
    assert len(rows) == 3
    assert rows[2][0] == "'+evil"


def test_export_limits(member_client: TestClient):
    record = make_prospect().model_dump()

    assert member_client.post("/api/export/csv", json={"records": []}).status_code == 422
    assert member_client.post("/api/export/csv", json={"records": [record] * 1001}).status_code == 422
