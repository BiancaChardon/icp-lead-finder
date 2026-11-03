import csv
import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import CSRF_HEADER
from app.excel_import import MAX_UPLOAD_BYTES
from app.models import AuditEvent, SavedLead, User

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADERS = ["Company", "First Name", "Last Name", "Job Title", "Email", "Phone", "Employees"]


def workbook_bytes(headers: list[str], rows: list[list[object]], formula_cells: dict[tuple[int, int], str] | None = None) -> bytes:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    for (row_number, column), formula in (formula_cells or {}).items():
        sheet.cell(row_number, column, formula)
    buffer = io.BytesIO()
    book.save(buffer)
    book.close()
    return buffer.getvalue()


def upload(
    client: TestClient,
    path: str,
    payload: bytes,
    name: str = "leads.xlsx",
    headers: dict[str, str] | None = None,
    **data: str,
):
    return client.post(
        path,
        files={"file": (name, payload, XLSX_TYPE)},
        data=data or None,
        headers=headers,
    )


def test_valid_spreadsheet_imports_real_leads(member_client: TestClient, db: Session):
    payload = workbook_bytes(
        ["Company Name", "First Name", "Last Name", "Title", "Email Address", "Phone Number", "Website", "Industry", "Employees", "City", "Province", "Country", "Data Source"],
        [[
            "Northgate Health, LLC",
            "Avery",
            "Lang",
            "CIO",
            "Avery.Lang@harborline-health.example",
            "410-555-0101",
            "harborline-health.example",
            "Healthcare",
            420,
            "Baltimore",
            "MD",
            "United States",
            "Sample spreadsheet (fictional)",
        ]],
    )

    preview = upload(member_client, "/api/leads/import/preview", payload)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["ready_records"] == 1
    assert body["invalid_records"] == 0
    assert body["columns"][0]["field"] == "company_name"
    assert body["rows"][0]["email"] == "avery.lang@harborline-health.example"
    assert body["rows"][0]["state"] == "MD"
    assert body["rows"][0]["company_website"] == "https://harborline-health.example"

    imported = upload(member_client, "/api/leads/import", payload)
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"imported": 1, "updated": 0, "skipped_duplicates": 0, "rejected": 0}

    lead = db.scalar(select(SavedLead))
    assert lead is not None
    assert lead.provider == "excel_import"
    assert lead.is_demo is False
    assert lead.email_status == "unknown"
    assert lead.data_source == "Sample spreadsheet (fictional)"
    assert lead.company_name == "Northgate Health, LLC"
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "leads_imported")) is not None


def test_missing_optional_columns_still_import(member_client: TestClient, db: Session):
    payload = workbook_bytes(["Company", "Last Name"], [["Cedarline Clinics", "Bramley"]])

    preview = upload(member_client, "/api/leads/import/preview", payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["ready_records"] == 1
    assert preview.json()["rows"][0]["email"] is None

    assert upload(member_client, "/api/leads/import", payload).status_code == 200
    lead = db.scalar(select(SavedLead))
    assert lead is not None
    assert lead.email is None
    assert lead.email_status == "unavailable"
    assert lead.job_title is None


def test_alternative_column_names(member_client: TestClient):
    payload = workbook_bytes(
        ["Company Name", "Title", "Email Address", "Phone Number", "Employee Count", "Province"],
        [["Ironbridge Medical", "IT Director", "casey@ironbridge-medical.example", "410-555-0199", "1,200", "Virginia"]],
    )

    body = upload(member_client, "/api/leads/import/preview", payload).json()
    row = body["rows"][0]
    assert body["ready_records"] == 1
    assert row["job_title"] == "IT Director"
    assert row["employee_count"] == 1200
    assert row["state"] == "Virginia"
    assert row["phone"] == "410-555-0199"


def test_blank_rows_are_ignored(member_client: TestClient):
    payload = workbook_bytes(
        HEADERS,
        [
            ["Cedarline", "Riley", "Quinn", "CIO", "riley@cedarline.example", None, 10],
            [None, None, None, None, None, None, None],
            ["", "", "", "", "", "", ""],
            ["Oakridge", "Drew", "Shaw", "CTO", "drew@oakridge.example", None, 20],
        ],
    )

    body = upload(member_client, "/api/leads/import/preview", payload).json()
    assert body["blank_rows"] == 2
    assert body["total_rows"] == 4
    assert body["ready_records"] == 2
    assert body["invalid_records"] == 0


def test_invalid_email_is_rejected_without_blocking_valid_rows(member_client: TestClient, db: Session):
    payload = workbook_bytes(
        ["Company", "Email"],
        [["Good Clinic", "ada@good-clinic.example"], ["Bad Clinic", "not-an-email"]],
    )

    preview = upload(member_client, "/api/leads/import/preview", payload).json()
    assert preview["ready_records"] == 1
    assert preview["invalid_records"] == 1
    invalid = next(row for row in preview["rows"] if row["status"] == "invalid")
    assert invalid["errors"] == ["Email is not a valid address."]

    result = upload(member_client, "/api/leads/import", payload).json()
    assert result["imported"] == 1
    assert result["rejected"] == 1
    emails = set(db.scalars(select(SavedLead.email)))
    assert emails == {"ada@good-clinic.example"}

    report = upload(member_client, "/api/leads/import/errors", payload)
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(report.text.lstrip("\ufeff"))))
    assert "Email is not a valid address." in rows[1][1]


def test_invalid_employee_counts(member_client: TestClient):
    payload = workbook_bytes(
        ["Company", "Employees"],
        [["One", "many"], ["Two", -3], ["Three", 12.5], ["Four", 15]],
    )

    body = upload(member_client, "/api/leads/import/preview", payload).json()
    assert body["invalid_records"] == 3
    assert body["ready_records"] == 1
    assert all("Employees must be a whole number" in error for row in body["rows"] if row["status"] == "invalid" for error in row["errors"])


def test_duplicate_rows_and_reupload_keep_the_same_record(member_client: TestClient, db: Session):
    payload = workbook_bytes(
        ["Company", "Email", "Job Title"],
        [
            ["First Clinic", "same@person.example", "CIO"],
            ["Second Clinic", "same@person.example", "CTO"],
        ],
    )

    preview = upload(member_client, "/api/leads/import/preview", payload).json()
    assert preview["ready_records"] == 1
    assert preview["repeated_rows"] == 1

    first = upload(member_client, "/api/leads/import", payload)
    assert first.json()["imported"] == 1
    record_id = db.scalar(select(SavedLead.provider_record_id))

    again = upload(member_client, "/api/leads/import/preview", payload).json()
    assert again["existing_duplicates"] == 1
    assert again["repeated_rows"] == 1
    assert again["ready_records"] == 0
    assert {row["provider_record_id"] for row in again["rows"]} == {record_id}

    second = upload(member_client, "/api/leads/import", payload).json()
    assert second == {"imported": 0, "updated": 0, "skipped_duplicates": 2, "rejected": 0}
    assert db.scalar(select(func.count()).select_from(SavedLead)) == 1
    assert db.scalar(select(SavedLead.job_title)) == "CIO"


def test_overwrite_updates_only_when_requested(member_client: TestClient, db: Session):
    original = workbook_bytes(["Email", "Company", "Job Title"], [["pat@update.example", "Old Clinic", "CIO"]])
    revised = workbook_bytes(["Email", "Company", "Job Title"], [["pat@update.example", "New Clinic", "CTO"]])
    assert upload(member_client, "/api/leads/import", original).json()["imported"] == 1

    skipped = upload(member_client, "/api/leads/import", revised).json()
    assert skipped["imported"] == 0
    assert skipped["updated"] == 0
    assert db.scalar(select(SavedLead.company_name)) == "Old Clinic"

    updated = upload(member_client, "/api/leads/import", revised, overwrite="true").json()
    assert updated == {"imported": 0, "updated": 1, "skipped_duplicates": 0, "rejected": 0}
    assert db.scalar(select(func.count()).select_from(SavedLead)) == 1
    db.expire_all()
    lead = db.scalar(select(SavedLead))
    assert lead is not None
    assert lead.company_name == "New Clinic"
    assert lead.job_title == "CTO"


def test_manual_mapping_for_unrecognized_headers(member_client: TestClient):
    payload = workbook_bytes(["Firm", "Office"], [["Pinecrest Health", "Rockville"]])
    unmapped = upload(member_client, "/api/leads/import/preview", payload)
    assert unmapped.status_code == 422

    mapped = upload(
        member_client,
        "/api/leads/import/preview",
        payload,
        mapping=json.dumps({"Firm": "company_name", "Office": "city"}),
    )
    assert mapped.status_code == 200, mapped.text
    row = mapped.json()["rows"][0]
    assert row["company_name"] == "Pinecrest Health"
    assert row["city"] == "Rockville"
    assert mapped.json()["ready_records"] == 1


def test_formulas_are_not_executed(member_client: TestClient, db: Session):
    payload = workbook_bytes(
        ["Company", "Employees"],
        [["Formula Clinic", None]],
        formula_cells={(2, 2): "=1+1"},
    )

    body = upload(member_client, "/api/leads/import/preview", payload).json()
    assert body["invalid_records"] == 1
    assert "formula" in body["rows"][0]["errors"][0].lower()
    assert body["rows"][0]["employee_count"] is None

    result = upload(member_client, "/api/leads/import", payload).json()
    assert result["imported"] == 0
    assert db.scalar(select(func.count()).select_from(SavedLead)) == 0


def test_error_report_escapes_formula_text(member_client: TestClient):
    payload = workbook_bytes(["Company", "Email"], [["=cmd|' /C calc'!A0", "not-an-email"]])

    report = upload(member_client, "/api/leads/import/errors", payload)
    assert report.status_code == 200
    rows = list(csv.reader(io.StringIO(report.text.lstrip("\ufeff"))))
    assert rows[1][2] == "'=cmd|' /C calc'!A0"


def test_corrupted_xlsx_is_rejected(member_client: TestClient):
    response = upload(member_client, "/api/leads/import/preview", b"PK\x03\x04this is not a workbook")
    assert response.status_code == 422
    assert "not a valid" in response.json()["detail"].lower() or "corrupted" in response.json()["detail"].lower()


def test_legacy_xls_is_rejected(member_client: TestClient):
    by_name = upload(member_client, "/api/leads/import/preview", b"not really xls", name="leads.xls")
    assert by_name.status_code == 415
    assert ".xls" in by_name.json()["detail"]

    by_content = upload(member_client, "/api/leads/import/preview", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", name="leads.xlsx")
    assert by_content.status_code == 415


def test_file_over_the_size_limit_is_rejected(member_client: TestClient):
    response = upload(member_client, "/api/leads/import/preview", b"x" * (MAX_UPLOAD_BYTES + 1))
    assert response.status_code == 413


def test_sheet_over_the_row_limit_is_rejected(member_client: TestClient):
    book = Workbook(write_only=True)
    sheet = book.create_sheet()
    sheet.append(["Company", "Email"])
    for number in range(5001):
        sheet.append([f"Company {number}", f"person{number}@row-limit.example"])
    buffer = io.BytesIO()
    book.save(buffer)
    book.close()

    response = upload(member_client, "/api/leads/import/preview", buffer.getvalue())
    assert response.status_code == 422
    assert "5,000" in response.json()["detail"]


def test_failed_commit_rolls_back_the_import(member_client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch):
    original = workbook_bytes(["Company"], [["Kept Clinic"]])
    assert upload(member_client, "/api/leads/import", original).json()["imported"] == 1

    def fail(self: Session) -> None:
        raise IntegrityError("INSERT INTO saved_leads", {}, Exception("conflict"))

    monkeypatch.setattr(Session, "commit", fail)
    response = upload(member_client, "/api/leads/import", workbook_bytes(["Company"], [["Lost Clinic"]]))
    assert response.status_code == 409

    db.rollback()
    names = set(db.scalars(select(SavedLead.company_name)))
    assert names == {"Kept Clinic"}


def test_import_preserves_leads_from_other_providers(member_client: TestClient, db: Session):
    user = db.scalar(select(User).where(User.email == "member@example.com"))
    assert user is not None
    db.add(
        SavedLead(
            user_id=user.id,
            provider="mock",
            provider_record_id="demo-1",
            is_demo=True,
            data_source="Demo data (mock provider)",
            company_name="Demo Clinic",
            email_status="unavailable",
            phone_status="unavailable",
        )
    )
    db.commit()

    upload(member_client, "/api/leads/import", workbook_bytes(["Company"], [["Imported Clinic"]]))
    db.expire_all()
    rows = db.scalars(select(SavedLead).order_by(SavedLead.id)).all()
    assert [(row.provider, row.company_name, row.is_demo) for row in rows] == [
        ("mock", "Demo Clinic", True),
        ("excel_import", "Imported Clinic", False),
    ]


def test_import_requires_login(client: TestClient):
    response = upload(client, "/api/leads/import/preview", workbook_bytes(["Company"], [["Clinic"]]))
    assert response.status_code == 401


def test_import_requires_csrf_token(member_client: TestClient):
    payload = workbook_bytes(["Company"], [["Clinic"]])
    del member_client.headers[CSRF_HEADER]
    assert upload(member_client, "/api/leads/import", payload).status_code == 403

    member_client.headers[CSRF_HEADER] = "forged"
    assert upload(member_client, "/api/leads/import", payload).status_code == 403


def test_import_rejects_untrusted_origin(member_client: TestClient):
    payload = workbook_bytes(["Company"], [["Clinic"]])
    response = upload(
        member_client,
        "/api/leads/import",
        payload,
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Origin not allowed"
