"""Contact search against the demo provider and imported saved leads.

The workbook is built in this test and imported into the isolated test database.
The running demo database is not used.
"""

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contact_search import normalize_phone
from app.models import SavedLead
from app.providers.base import ProspectProvider, ProspectQuery, UnsupportedQueryError
from app.providers.mock import MockProvider
from app.schemas import SearchCriteria
from tests.test_excel_import import upload, workbook_bytes
from tests.test_mock_provider import all_results

HEADERS = [
    "Company Name",
    "First Name",
    "Last Name",
    "Job Title",
    "Email Address",
    "Phone Number",
    "Website",
    "Industry",
    "Employees",
    "City",
    "State",
    "Country",
    "Data Source",
]
SOURCE = "Contact search sample (fictional)"


def contact_rows() -> list[list[object]]:
    rows: list[list[object]] = [
        ["Larkspur Health", "Marisol", "Okoye", "Chief Information Officer (CIO)", "marisol.okoye@larkspur-health.example", "(410) 555-0142", "larkspur-health.example", "Healthcare", 420, "Baltimore", "MD", "United States", SOURCE],
        ["Northwind Clinics", "Marisol", "Chen", "IT Director", "marisol.chen@northwind-clinics.example", "410-555-0143", "northwind-clinics.example", "Healthcare", 180, "Columbia", "MD", "United States", SOURCE],
        ["Pellham Manufacturing", "Helen", "Okoye", "VP of Operations", "helen.okoye@pellham-manufacturing.example", "804-555-0144", "pellham-manufacturing.example", "Manufacturing", 900, "Richmond", "VA", "United States", SOURCE],
    ]
    for number in range(1, 48):
        rows.append(
            [
                f"Filler Company {number:02d}",
                f"Quincy{number:02d}",
                f"Hale{number:02d}",
                "IT Manager",
                f"quincy{number:02d}.hale{number:02d}@filler-{number:02d}.example",
                f"301-555-{2000 + number}",
                f"filler-{number:02d}.example",
                "Software",
                100 + number,
                "Austin",
                "TX",
                "United States",
                SOURCE,
            ]
        )
    rows[-1][4] = None
    assert len(rows) == 50
    return rows


@pytest.fixture
def imported_workbook(member_client: TestClient) -> bytes:
    payload = workbook_bytes(HEADERS, contact_rows())
    response = upload(member_client, "/api/leads/import", payload)
    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 50
    return payload


def saved(client: TestClient, **params: str) -> dict:
    response = client.get("/api/leads", params={"per_page": 50, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_search_by_first_name(member_client: TestClient, imported_workbook: bytes):
    body = saved(member_client, first_name="mari")

    assert body["total"] == 2
    assert {item["first_name"] for item in body["items"]} == {"Marisol"}


def test_search_by_last_name(member_client: TestClient, imported_workbook: bytes):
    body = saved(member_client, last_name="OKO")

    assert body["total"] == 2
    assert {item["last_name"] for item in body["items"]} == {"Okoye"}


def test_search_by_first_and_last_name(member_client: TestClient, imported_workbook: bytes):
    body = saved(member_client, first_name="Marisol", last_name="Okoye")

    assert body["total"] == 1
    person = body["items"][0]
    assert person["company_name"] == "Larkspur Health"
    assert person["job_title"] == "Chief Information Officer (CIO)"
    assert person["email"] == "marisol.okoye@larkspur-health.example"
    assert person["phone"] == "(410) 555-0142"
    assert person["company_website"] == "https://larkspur-health.example"
    assert person["city"] == "Baltimore"


def test_search_by_email_is_case_insensitive(member_client: TestClient, imported_workbook: bytes):
    body = saved(member_client, email="MARISOL.OKOYE@LARKSPUR-HEALTH.EXAMPLE")

    assert body["total"] == 1
    assert body["items"][0]["last_name"] == "Okoye"


def test_search_by_partial_email(member_client: TestClient, imported_workbook: bytes):
    body = saved(member_client, email="okoye@larkspur")

    assert body["total"] == 1
    assert body["items"][0]["email"] == "marisol.okoye@larkspur-health.example"


def test_search_by_phone_number(member_client: TestClient, imported_workbook: bytes):
    body = saved(member_client, phone="4105550142")

    assert body["total"] == 1
    assert body["items"][0]["company_name"] == "Larkspur Health"


@pytest.mark.parametrize("phone", ["+1 (410) 555-0142", "410.555.0142", "1-410-555-0142"])
def test_formatted_and_unformatted_phone_numbers_match(member_client: TestClient, imported_workbook: bytes, phone: str):
    body = saved(member_client, phone=phone)

    assert body["total"] == 1
    assert body["items"][0]["phone"] == "(410) 555-0142"


def test_contact_and_company_filters_combine(member_client: TestClient, imported_workbook: bytes):
    narrowed = saved(member_client, first_name="Marisol", company_name="Larkspur", industry="health")
    broader = saved(member_client, first_name="Marisol", industry="Healthcare")

    assert narrowed["total"] == 1
    assert narrowed["items"][0]["last_name"] == "Okoye"
    assert broader["total"] == 2


def test_empty_contact_fields_do_not_filter(member_client: TestClient, imported_workbook: bytes):
    body = saved(member_client, first_name="  ", last_name="", email="", phone="   ")

    assert body["total"] == 50


def test_no_contact_match_leaves_saved_leads_in_place(member_client: TestClient, db: Session, imported_workbook: bytes):
    missing = saved(member_client, first_name="Zzqx")
    wildcard = saved(member_client, email="%")

    assert missing["total"] == 0
    assert wildcard["total"] == 0
    assert saved(member_client)["total"] == 50
    assert db.scalar(select(func.count()).select_from(SavedLead)) == 50


def test_reimport_does_not_duplicate_and_saved_search_results_persist(member_client: TestClient, imported_workbook: bytes):
    again = upload(member_client, "/api/leads/import", imported_workbook)

    assert again.status_code == 200, again.text
    assert again.json()["imported"] == 0
    assert again.json()["skipped_duplicates"] == 50
    assert saved(member_client, email="marisol.okoye@larkspur-health.example")["total"] == 1

    found = member_client.post(
        "/api/search", json={"criteria": {"employee_min": 1}, "per_page": 10, "record_history": False}
    ).json()["results"]
    person = next(row for row in found if row["email"] and row["phone"])
    first = member_client.post("/api/leads", json={"leads": [person]})
    second = member_client.post("/api/leads", json={"leads": [person]})

    assert first.json()["saved"] == 1
    assert second.json()["already_saved"] == 1
    listed = saved(member_client, email=person["email"])
    assert listed["total"] == 1
    assert listed["items"][0]["provider_record_id"] == person["provider_record_id"]
    assert saved(member_client)["total"] == 51


def test_saved_phone_without_digits_is_rejected(member_client: TestClient, imported_workbook: bytes):
    response = member_client.get("/api/leads", params={"phone": "call me"})

    assert response.status_code == 422
    assert saved(member_client)["total"] == 50


class _NoContactProvider(ProspectProvider):
    name = "nocontact"
    display_name = "No contact search"

    def search(self, query: ProspectQuery):
        raise AssertionError("unsupported contact criteria must be rejected before search")


def test_provider_without_contact_fields_does_not_pretend_to_search(member_client: TestClient, app: FastAPI):
    app.state.provider = _NoContactProvider()

    response = member_client.post("/api/search", json={"criteria": {"email": "a@b.example"}})

    assert response.status_code == 422
    assert "email address" in response.json()["detail"]
    assert "Saved Leads" in response.json()["detail"]


def test_mock_provider_matches_contact_fields():
    provider = MockProvider()
    person = next(row for row in all_results(provider, employee_min=1) if row.email and row.phone)
    national = normalize_phone(person.phone)
    email_part = person.email.split("@")[0]

    by_first = all_results(provider, first_name=person.first_name[:4])
    by_last = all_results(provider, last_name=person.last_name.swapcase())
    by_both = all_results(provider, first_name=person.first_name, last_name=person.last_name)
    by_email = all_results(provider, email=person.email.upper())
    by_partial_email = all_results(provider, email=email_part.upper())
    by_phone = all_results(provider, phone=national)
    by_formatted_phone = all_results(provider, phone=f"+1 ({national[:3]}) {national[3:6]}-{national[6:]}")
    combined = all_results(
        provider,
        first_name=person.first_name,
        company_name=person.company_name,
        industry=person.industry,
    )
    company_only = all_results(provider, industry=person.industry)
    with_blank_contact = provider.search(
        ProspectQuery(criteria=SearchCriteria(industry=person.industry, first_name="   "), page=1, per_page=50)
    )

    assert person.provider_record_id in {row.provider_record_id for row in by_first}
    token = person.first_name[:4].casefold()
    assert all(token in f"{row.first_name or ''} {row.last_name or ''}".casefold() for row in by_first)
    assert person.provider_record_id in {row.provider_record_id for row in by_last}
    assert {row.provider_record_id for row in by_both} <= {row.provider_record_id for row in by_first}
    assert person.provider_record_id in {row.provider_record_id for row in by_email}
    assert all(email_part.casefold() in (row.email or "").casefold() for row in by_partial_email)
    assert [row.provider_record_id for row in by_phone] == [row.provider_record_id for row in by_formatted_phone]
    assert person.provider_record_id in {row.provider_record_id for row in by_phone}
    assert person.provider_record_id in {row.provider_record_id for row in combined}
    assert all(person.company_name.lower() in (row.company_name or "").lower() for row in combined)
    assert with_blank_contact.total == len(company_only)
    assert all_results(provider, email="missing-person@nowhere.example") == []
    with pytest.raises(UnsupportedQueryError, match="first name"):
        _NoContactProvider().validate_query(
            ProspectQuery(criteria=SearchCriteria(first_name="Avery"), page=1, per_page=25)
        )


SOPHIA_EMAIL = "sophia.price@fernfield.example"
ETHAN_EMAIL = "ethan.cole@blueharbordental.example"


@pytest.fixture
def sophia_imported(member_client: TestClient) -> None:
    rows = [
        ["Fern & Field Wellness", "Sophia", "Price", "Office Manager", SOPHIA_EMAIL, "202-555-0106", "fernfield.example", "Wellness", 40, "Fulton", "MD", "United States", SOURCE],
        ["Blue Harbor Dental Group", "Ethan", "Cole", "Practice Manager", ETHAN_EMAIL, "202-555-0101", "blueharbordental.example", "Healthcare", 25, "Baltimore", "MD", "United States", SOURCE],
    ]
    response = upload(member_client, "/api/leads/import", workbook_bytes(HEADERS, rows))
    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 2


def _emails(body: dict) -> set[str]:
    return {item["email"] for item in body["items"]}


@pytest.mark.parametrize(
    "params",
    [
        {"first_name": "Sophia"},
        {"last_name": "Price"},
        {"first_name": "Sophia Price"},
        {"first_name": "SOPHIA PRICE"},
        {"first_name": "Price, Sophia"},
        {"first_name": "  sophia    price  "},
        {"first_name": "Price Sophia"},
        {"full_name": "Sophia Price"},
        {"full_name": "Price, Sophia"},
        {"email": SOPHIA_EMAIL},
        {"email": "price@fernfield"},
        {"phone": "202-555-0106"},
        {"phone": "2025550106"},
    ],
)
def test_sophia_price_name_email_and_phone_searches(member_client: TestClient, sophia_imported: None, params: dict):
    body = saved(member_client, **params)

    assert body["total"] == 1
    assert body["items"][0]["email"] == SOPHIA_EMAIL
    assert body["items"][0]["first_name"] == "Sophia"
    assert body["items"][0]["last_name"] == "Price"


def test_sophia_combined_with_her_industry_and_company(member_client: TestClient, sophia_imported: None):
    wellness = saved(member_client, full_name="Sophia Price", industry="Wellness")
    healthcare = saved(member_client, full_name="Sophia Price", industry="Healthcare")
    company = saved(member_client, company_name="Fern & Field Wellness")
    ethan = saved(member_client, full_name="Ethan Cole", industry="Healthcare")

    assert _emails(wellness) == {SOPHIA_EMAIL}
    assert healthcare["total"] == 0
    assert _emails(company) == {SOPHIA_EMAIL}
    assert _emails(ethan) == {ETHAN_EMAIL}


def test_every_row_in_the_fifty_prospect_workbook_is_searchable(member_client: TestClient, imported_workbook: bytes):
    for row in contact_rows():
        if row[4]:
            body = saved(member_client, email=str(row[4]))
        else:
            body = saved(member_client, first_name=str(row[1]), last_name=str(row[2]))
        assert body["total"] == 1
        assert body["items"][0]["company_name"] == row[0]


def test_phone_normalization_ignores_formatting():
    assert normalize_phone("+1 (410) 555-0142") == normalize_phone("410.555.0142") == "4105550142"
    assert re.fullmatch(r"\d{10}", normalize_phone("1-410-555-0142"))
