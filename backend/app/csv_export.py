import csv
import io
from collections.abc import Iterable

from app.schemas import Prospect

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

COLUMNS: list[tuple[str, str]] = [
    ("Company", "company_name"),
    ("First Name", "first_name"),
    ("Last Name", "last_name"),
    ("Job Title", "job_title"),
    ("Email", "email"),
    ("Email Status", "email_status"),
    ("Phone", "phone"),
    ("Phone Status", "phone_status"),
    ("Website", "company_website"),
    ("Industry", "industry"),
    ("Employees", "employee_count"),
    ("City", "city"),
    ("State", "state"),
    ("Country", "country"),
    ("Data Source", "data_source"),
    ("Demo Data", "is_demo"),
]


def escape_cell(value: object) -> str:
    """Neutralize spreadsheet formulas (CSV injection) in exported values."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def prospects_to_csv(records: Iterable[Prospect]) -> str:
    buffer = io.StringIO()
    buffer.write("\ufeff")  # UTF-8 BOM so Excel detects the encoding
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow([header for header, _ in COLUMNS])
    for record in records:
        writer.writerow([escape_cell(getattr(record, field)) for _, field in COLUMNS])
    return buffer.getvalue()
