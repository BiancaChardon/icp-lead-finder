"""Parse .xlsx lead lists into saved-lead records.

openpyxl reads stored cell values only. Formulas are rejected and never
evaluated. Uploaded bytes are parsed in memory and are not written to disk.
"""

import hashlib
import json
import logging
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from openpyxl import load_workbook
from openpyxl.cell.read_only import ReadOnlyCell
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import record_event
from app.csv_export import escape_cell
from app.models import SavedLead, User
from app.schemas import (
    MAX_EMPLOYEES,
    ImportColumn,
    ImportField,
    ImportPreview,
    ImportPreviewRow,
    ImportResult,
)

logger = logging.getLogger("app")

PROVIDER = "excel_import"
DEFAULT_DATA_SOURCE = "Excel import"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_DATA_ROWS = 5000
MAX_COLUMNS = 50
PREVIEW_ROW_LIMIT = 100
XLS_MAGIC = b"\xd0\xcf\x11\xe0"
XLSX_MAGIC = b"PK"

FIELDS: dict[str, str] = {
    "company_name": "Company",
    "first_name": "First name",
    "last_name": "Last name",
    "job_title": "Job title",
    "email": "Email",
    "phone": "Phone",
    "company_website": "Website",
    "industry": "Industry",
    "employee_count": "Employees",
    "city": "City",
    "state": "State",
    "country": "Country",
    "data_source": "Data source",
}

LIMITS: dict[str, int] = {
    "company_name": 200,
    "first_name": 100,
    "last_name": 100,
    "job_title": 200,
    "email": 320,
    "phone": 50,
    "company_website": 500,
    "industry": 100,
    "city": 100,
    "state": 100,
    "country": 100,
    "data_source": 100,
}

ALIASES: dict[str, str] = {
    "company": "company_name",
    "company name": "company_name",
    "organization": "company_name",
    "organisation": "company_name",
    "account": "company_name",
    "account name": "company_name",
    "first name": "first_name",
    "firstname": "first_name",
    "given name": "first_name",
    "last name": "last_name",
    "lastname": "last_name",
    "surname": "last_name",
    "family name": "last_name",
    "job title": "job_title",
    "jobtitle": "job_title",
    "title": "job_title",
    "position": "job_title",
    "email": "email",
    "email address": "email",
    "e mail": "email",
    "e mail address": "email",
    "work email": "email",
    "phone": "phone",
    "phone number": "phone",
    "telephone": "phone",
    "mobile": "phone",
    "mobile phone": "phone",
    "website": "company_website",
    "web site": "company_website",
    "company website": "company_website",
    "company url": "company_website",
    "url": "company_website",
    "industry": "industry",
    "employees": "employee_count",
    "employee count": "employee_count",
    "employee number": "employee_count",
    "number of employees": "employee_count",
    "company size": "employee_count",
    "city": "city",
    "state": "state",
    "province": "state",
    "state province": "state",
    "country": "country",
    "data source": "data_source",
    "source": "data_source",
}

class ImportRejected(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class ValidRow:
    row_number: int
    provider_record_id: str
    company_name: str | None
    first_name: str | None
    last_name: str | None
    job_title: str | None
    email: str | None
    phone: str | None
    company_website: str | None
    industry: str | None
    employee_count: int | None
    city: str | None
    state: str | None
    country: str | None
    data_source: str

    def display(self) -> dict[str, object]:
        return {
            "provider_record_id": self.provider_record_id,
            "company_name": self.company_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "job_title": self.job_title,
            "email": self.email,
            "phone": self.phone,
            "company_website": self.company_website,
            "industry": self.industry,
            "employee_count": self.employee_count,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "data_source": self.data_source,
        }


@dataclass
class InvalidRow:
    row_number: int
    errors: list[str]
    values: dict[str, object] = field(default_factory=dict)


@dataclass
class ParsedSheet:
    sheet_name: str
    columns: list[tuple[int, str, str | None]]
    total_rows: int
    blank_rows: int
    valid_rows: list[ValidRow]
    invalid_rows: list[InvalidRow]


def import_fields() -> list[ImportField]:
    return [ImportField(key=key, label=label) for key, label in FIELDS.items()]


def parse_mapping(raw: str | None) -> dict[str, str] | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImportRejected("Column mapping must be a JSON object.") from exc
    if not isinstance(parsed, dict):
        raise ImportRejected("Column mapping must be a JSON object.")
    mapping: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ImportRejected("Column mapping must map column names to field names.")
        if len(key) > 200 or len(value) > 50:
            raise ImportRejected("Column mapping contains a value that is too long.")
        mapping[key] = value
    return mapping


def read_upload(filename: str | None, payload: bytes) -> None:
    """Validate the upload before it is parsed. The caller supplies already-read bytes."""
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ImportRejected("The file exceeds the 10 MB limit.", 413)
    if not payload:
        raise ImportRejected("The file is empty.")

    safe_name = Path(filename or "").name
    suffix = Path(safe_name).suffix.lower()
    if suffix == ".xls" or payload.startswith(XLS_MAGIC):
        raise ImportRejected(
            "Legacy .xls files are not supported. Save the spreadsheet as .xlsx and try again.",
            415,
        )
    if suffix != ".xlsx":
        raise ImportRejected("Only .xlsx spreadsheets can be imported.", 415)
    if not payload.startswith(XLSX_MAGIC):
        raise ImportRejected("The file is not a valid .xlsx spreadsheet.")
    _reject_unsafe_package(payload)


def _reject_unsafe_package(payload: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(payload)) as package:
            infos = package.infolist()
            if not any(info.filename == "[Content_Types].xml" for info in infos):
                raise ImportRejected("The spreadsheet is corrupted or is not a valid .xlsx file.")
            if any(info.filename.lower().endswith("vbaproject.bin") for info in infos):
                raise ImportRejected("Spreadsheets with macros are not accepted.", 415)
            expanded = sum(info.file_size for info in infos)
    except ImportRejected:
        raise
    except zipfile.BadZipFile as exc:
        raise ImportRejected("The spreadsheet is corrupted or is not a valid .xlsx file.") from exc
    if expanded > MAX_UNCOMPRESSED_BYTES:
        raise ImportRejected("The spreadsheet expands beyond the allowed size.", 413)


def load_sheet(filename: str | None, payload: bytes, mapping: dict[str, str] | None) -> ParsedSheet:
    read_upload(filename, payload)
    return _parse_sheet(payload, mapping)


def _parse_sheet(payload: bytes, mapping: dict[str, str] | None) -> ParsedSheet:
    workbook = _open_workbook(payload)
    try:
        worksheet = workbook.worksheets[0] if workbook.worksheets else None
        if worksheet is None:
            raise ImportRejected("The spreadsheet has no sheets.")
        rows = worksheet.iter_rows()
        header_cells = next(rows, None)
        if header_cells is None:
            raise ImportRejected("The spreadsheet has no column headers.")
        columns = _resolve_columns(header_cells, mapping)
        if not any(field_name for _, _, field_name in columns):
            raise ImportRejected("None of the column headers match a lead field. Map at least one column.")
        return _read_rows(worksheet.title or "Sheet1", columns, rows)
    finally:
        workbook.close()


def classify_preview(parsed: ParsedSheet, existing_ids: set[str]) -> ImportPreview:
    ready = 0
    existing_duplicates = 0
    repeated_rows = 0
    seen: set[str] = set()
    classified: list[ImportPreviewRow] = []

    for row in parsed.invalid_rows:
        classified.append(
            ImportPreviewRow(row_number=row.row_number, status="invalid", errors=row.errors, **_preview_values(row.values))
        )

    for row in parsed.valid_rows:
        if row.provider_record_id in seen:
            repeated_rows += 1
            classified.append(
                ImportPreviewRow(
                    row_number=row.row_number,
                    status="duplicate",
                    duplicate_reason="in_file",
                    errors=["This row repeats an earlier row in the spreadsheet."],
                    **row.display(),
                )
            )
            continue
        seen.add(row.provider_record_id)
        if row.provider_record_id in existing_ids:
            existing_duplicates += 1
            classified.append(
                ImportPreviewRow(
                    row_number=row.row_number,
                    status="duplicate",
                    duplicate_reason="already_saved",
                    errors=["A saved lead already matches this row."],
                    **row.display(),
                )
            )
            continue
        ready += 1
        classified.append(ImportPreviewRow(row_number=row.row_number, status="ready", errors=[], **row.display()))

    duplicates = existing_duplicates + repeated_rows
    shown = classified[:PREVIEW_ROW_LIMIT]
    unmapped = [header for _, header, field_name in parsed.columns if field_name is None and header]
    return ImportPreview(
        sheet_name=parsed.sheet_name,
        total_rows=parsed.total_rows,
        blank_rows=parsed.blank_rows,
        valid_records=len(parsed.valid_rows),
        invalid_records=len(parsed.invalid_rows),
        duplicate_records=duplicates,
        existing_duplicates=existing_duplicates,
        repeated_rows=repeated_rows,
        ready_records=ready,
        columns=[ImportColumn(header=header, field=field_name) for _, header, field_name in parsed.columns],
        unmapped_headers=unmapped,
        fields=import_fields(),
        rows=shown,
        rows_shown=len(shown),
        rows_omitted=max(0, len(classified) - len(shown)),
    )


def existing_record_ids(db: Session, user: User, record_ids: set[str]) -> set[str]:
    if not record_ids:
        return set()
    rows = db.scalars(
        select(SavedLead.provider_record_id).where(
            SavedLead.user_id == user.id,
            SavedLead.provider == PROVIDER,
            SavedLead.provider_record_id.in_(record_ids),
        )
    )
    return set(rows)


def save_rows(db: Session, user: User, parsed: ParsedSheet, *, overwrite: bool) -> ImportResult:
    record_ids = {row.provider_record_id for row in parsed.valid_rows}
    current_rows = db.scalars(
        select(SavedLead).where(
            SavedLead.user_id == user.id,
            SavedLead.provider == PROVIDER,
            SavedLead.provider_record_id.in_(record_ids),
        )
    ).all() if record_ids else []
    existing = {row.provider_record_id: row for row in current_rows}

    imported = 0
    updated = 0
    skipped = 0
    seen: set[str] = set()
    try:
        for row in parsed.valid_rows:
            if row.provider_record_id in seen:
                skipped += 1
                continue
            seen.add(row.provider_record_id)
            current = existing.get(row.provider_record_id)
            if current is None:
                db.add(_new_lead(user.id, row))
                imported += 1
            elif overwrite:
                _apply_row(current, row)
                updated += 1
            else:
                skipped += 1
        record_event(
            db,
            "leads_imported",
            actor_user_id=user.id,
            target_type="saved_lead",
            details={
                "imported": imported,
                "updated": updated,
                "skipped_duplicates": skipped,
                "rejected": len(parsed.invalid_rows),
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.error("Excel import hit a uniqueness conflict")
        raise ImportRejected(
            "This import conflicts with leads saved at the same time. Nothing from this file was saved.",
            409,
        ) from None
    except Exception:
        db.rollback()
        logger.error("Excel import failed (%s)", "database write")
        raise ImportRejected("The import could not be saved. No leads were changed.", 500) from None

    return ImportResult(
        imported=imported,
        updated=updated,
        skipped_duplicates=skipped,
        rejected=len(parsed.invalid_rows),
    )


def errors_csv(parsed: ParsedSheet) -> str:
    import csv
    from io import StringIO

    headers = ["Row", "Errors", *[FIELDS[name] for name in FIELDS]]
    buffer = StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(headers)
    for row in parsed.invalid_rows:
        values = [_cell(row.values.get(name)) for name in FIELDS]
        writer.writerow([row.row_number, escape_cell("; ".join(row.errors)), *values])
    return buffer.getvalue()


def _cell(value: object) -> str:
    return escape_cell(value)


def _open_workbook(payload: bytes):
    try:
        workbook = load_workbook(BytesIO(payload), read_only=True, data_only=False, keep_vba=False)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError, ValueError) as exc:
        logger.warning("Rejected spreadsheet (%s)", type(exc).__name__)
        raise ImportRejected("The spreadsheet is corrupted, password-protected, or not a valid .xlsx file.") from exc
    if getattr(workbook, "vba_archive", None) is not None:
        workbook.close()
        raise ImportRejected("Spreadsheets with macros are not accepted.", 415)
    return workbook


def _resolve_columns(
    header_cells: tuple[ReadOnlyCell, ...], mapping: dict[str, str] | None
) -> list[tuple[int, str, str | None]]:
    columns: list[tuple[int, str, str | None]] = []
    used: dict[str, str] = {}
    for index, cell in enumerate(header_cells[:MAX_COLUMNS]):
        if _is_formula(cell):
            raise ImportRejected("A column header contains a formula. Formulas are not imported.")
        header = _header_text(cell.value, index)
        if mapping is not None and header in mapping:
            field_name: str | None = mapping[header].strip() or None
            if field_name is not None and field_name not in FIELDS:
                raise ImportRejected(f'"{_short(header)}" is mapped to an unknown field.')
        else:
            field_name = ALIASES.get(_normalize_header(header)) if header else None
        if field_name is not None:
            if field_name in used:
                raise ImportRejected(f"{FIELDS[field_name]} is mapped from more than one column.")
            used[field_name] = header
        if header or field_name:
            columns.append((index, header, field_name))
    if len(header_cells) > MAX_COLUMNS:
        raise ImportRejected(f"Spreadsheets with more than {MAX_COLUMNS} columns are not supported.")
    return columns


def _read_rows(
    sheet_name: str, columns: list[tuple[int, str, str | None]], rows: Iterator[tuple[ReadOnlyCell, ...]]
) -> ParsedSheet:
    valid_rows: list[ValidRow] = []
    invalid_rows: list[InvalidRow] = []
    total = 0
    blanks = 0
    mapped = [(index, field_name) for index, _, field_name in columns if field_name]
    for offset, cells in enumerate(rows, start=2):
        total += 1
        if total > MAX_DATA_ROWS:
            raise ImportRejected(f"Spreadsheets are limited to {MAX_DATA_ROWS:,} rows.")
        extracted, errors, blank = _extract_row(cells, mapped)
        if blank:
            blanks += 1
            continue
        if errors:
            invalid_rows.append(InvalidRow(offset, errors, extracted))
            continue
        valid_rows.append(_valid_row(offset, extracted))
    if total == blanks:
        raise ImportRejected("The spreadsheet has no lead rows.")
    return ParsedSheet(sheet_name, columns, total, blanks, valid_rows, invalid_rows)


def _extract_row(
    cells: tuple[ReadOnlyCell, ...], mapped: list[tuple[int, str]]
) -> tuple[dict[str, object], list[str], bool]:
    values: dict[str, object] = {}
    errors: list[str] = []
    raw_present = False
    for index, field_name in mapped:
        cell = cells[index] if index < len(cells) else None
        if cell is not None and _is_formula(cell):
            errors.append(f"{FIELDS[field_name]} contains a formula. Formulas are not imported.")
            raw_present = True
            if isinstance(cell.value, str):
                values[field_name] = _short(cell.value)
            continue
        raw = None if cell is None else cell.value
        if _present(raw):
            raw_present = True
        try:
            values[field_name] = _parse_field(field_name, raw)
        except ValueError as exc:
            errors.append(str(exc))
            if _present(raw):
                values[field_name] = _short(str(raw).strip())
    if not raw_present and not errors:
        return {}, [], True
    if not errors and not _has_identity(values):
        errors.append("A company, name, or email is required.")
    return values, errors, False


def _valid_row(row_number: int, values: dict[str, object]) -> ValidRow:
    data_source = values.get("data_source") or DEFAULT_DATA_SOURCE
    if not isinstance(data_source, str) or not data_source.strip():
        data_source = DEFAULT_DATA_SOURCE
    row = ValidRow(
        row_number=row_number,
        provider_record_id="",
        company_name=_as_text(values.get("company_name")),
        first_name=_as_text(values.get("first_name")),
        last_name=_as_text(values.get("last_name")),
        job_title=_as_text(values.get("job_title")),
        email=_as_text(values.get("email")),
        phone=_as_text(values.get("phone")),
        company_website=_as_text(values.get("company_website")),
        industry=_as_text(values.get("industry")),
        employee_count=values.get("employee_count") if isinstance(values.get("employee_count"), int) else None,
        city=_as_text(values.get("city")),
        state=_as_text(values.get("state")),
        country=_as_text(values.get("country")),
        data_source=data_source,
    )
    row.provider_record_id = _record_id(row)
    return row


def _record_id(row: ValidRow) -> str:
    """Stable id so uploading the same person again matches the saved lead."""
    if row.email:
        identity = f"email:{row.email}"
    else:
        identity = "name:" + "|".join(
            part.casefold()
            for part in (row.company_name or "", row.first_name or "", row.last_name or "", row.phone or "")
        )
    return hashlib.sha256(identity.encode()).hexdigest()


def _new_lead(user_id: int, row: ValidRow) -> SavedLead:
    email_status, phone_status = _statuses(row.email, row.phone)
    return SavedLead(
        user_id=user_id,
        provider=PROVIDER,
        provider_record_id=row.provider_record_id,
        is_demo=False,
        data_source=row.data_source,
        company_name=row.company_name,
        first_name=row.first_name,
        last_name=row.last_name,
        job_title=row.job_title,
        email=row.email,
        email_status=email_status,
        phone=row.phone,
        phone_status=phone_status,
        company_website=row.company_website,
        industry=row.industry,
        employee_count=row.employee_count,
        city=row.city,
        state=row.state,
        country=row.country,
    )


def _apply_row(lead: SavedLead, row: ValidRow) -> None:
    email_status, phone_status = _statuses(row.email, row.phone)
    lead.is_demo = False
    lead.data_source = row.data_source
    lead.company_name = row.company_name
    lead.first_name = row.first_name
    lead.last_name = row.last_name
    lead.job_title = row.job_title
    lead.email = row.email
    lead.email_status = email_status
    lead.phone = row.phone
    lead.phone_status = phone_status
    lead.company_website = row.company_website
    lead.industry = row.industry
    lead.employee_count = row.employee_count
    lead.city = row.city
    lead.state = row.state
    lead.country = row.country


def _statuses(email: str | None, phone: str | None) -> tuple[str, str]:
    return ("unknown" if email else "unavailable", "unknown" if phone else "unavailable")


def _parse_field(field_name: str, raw: object) -> object:
    if field_name == "employee_count":
        return _parse_employees(raw)
    if field_name == "email":
        return _parse_email(raw)
    if field_name == "company_website":
        return _parse_website(raw)
    if field_name == "data_source":
        return _parse_text(raw, "Data source", LIMITS["data_source"])
    label = FIELDS[field_name]
    return _parse_text(raw, label, LIMITS[field_name])


def _parse_text(raw: object, label: str, limit: int) -> str | None:
    if not _present(raw):
        return None
    if isinstance(raw, bool):
        raise ValueError(f"{label} contains a value that is not text.")
    if isinstance(raw, datetime):
        text = raw.date().isoformat()
    elif isinstance(raw, date):
        text = raw.isoformat()
    elif isinstance(raw, float) and raw.is_integer():
        text = str(int(raw))
    elif isinstance(raw, int):
        text = str(raw)
    else:
        text = str(raw)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    if len(text) > limit:
        raise ValueError(f"{label} is longer than {limit} characters.")
    return text


def _parse_email(raw: object) -> str | None:
    text = _parse_text(raw, "Email", LIMITS["email"])
    if text is None:
        return None
    candidate = text.casefold()
    if any(mark in candidate for mark in (" ", "<", ">")):
        raise ValueError("Email is not a valid address.")
    try:
        normalized = validate_email(candidate, check_deliverability=False).normalized.casefold()
    except EmailNotValidError as exc:
        raise ValueError("Email is not a valid address.") from exc
    return normalized


def _parse_website(raw: object) -> str | None:
    text = _parse_text(raw, "Website", LIMITS["company_website"])
    if text is None:
        return None
    if text.lower().startswith(("http://", "https://")):
        return text.rstrip("/")
    if re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/[^\s]*)?", text):
        return "https://" + text.rstrip("/")
    return text


def _parse_employees(raw: object) -> int | None:
    if not _present(raw):
        return None
    if isinstance(raw, bool):
        raise ValueError("Employees must be a whole number zero or greater.")
    if isinstance(raw, int):
        number = raw
    elif isinstance(raw, float):
        if not raw.is_integer():
            raise ValueError("Employees must be a whole number zero or greater.")
        number = int(raw)
    elif isinstance(raw, str):
        text = raw.strip().replace(",", "")
        if not re.fullmatch(r"\d+", text):
            raise ValueError("Employees must be a whole number zero or greater.")
        number = int(text)
    else:
        raise ValueError("Employees must be a whole number zero or greater.")
    if number < 0 or number > MAX_EMPLOYEES:
        raise ValueError("Employees must be a whole number zero or greater.")
    return number


def _has_identity(values: dict[str, object]) -> bool:
    return any(_as_text(values.get(name)) for name in ("company_name", "first_name", "last_name", "email"))


def _present(raw: object) -> bool:
    if raw is None:
        return False
    if isinstance(raw, str) and raw.strip() == "":
        return False
    return True


def _is_formula(cell: ReadOnlyCell) -> bool:
    if getattr(cell, "data_type", None) == "f":
        return True
    value = getattr(cell, "value", None)
    return isinstance(value, str) and value.startswith("=")


def _header_text(raw: object, index: int) -> str:
    if not _present(raw) or isinstance(raw, bool):
        return f"Column {index + 1}" if _present(raw) else ""
    text = re.sub(r"\s+", " ", str(raw)).replace("\ufeff", "").strip()
    return _short(text, 200)


def _normalize_header(header: str) -> str:
    text = header.casefold().replace("\ufeff", "")
    text = text.replace("_", " ").replace("/", " ")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _short(text: str, limit: int = 200) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:limit]


def _as_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _preview_values(values: dict[str, object]) -> dict[str, object]:
    preview: dict[str, object] = {}
    for name in FIELDS:
        value = values.get(name)
        if name == "employee_count":
            preview[name] = value if isinstance(value, int) else None
        else:
            preview[name] = value if isinstance(value, str) else None
    return preview
