"""Shared matching rules for contact search.

Provider searches and saved-lead searches both use these rules. A provider that
does not store a field must reject that criterion instead of ignoring it.
"""

import re

from sqlalchemy import and_, case, func
from sqlalchemy.sql import Select

from app.models import SavedLead

CONTACT_SEARCH_FIELDS = ("full_name", "first_name", "last_name", "email", "phone")
CONTACT_FIELD_LABELS = {
    "full_name": "full name",
    "first_name": "first name",
    "last_name": "last name",
    "email": "email address",
    "phone": "phone number",
}


class ContactSearchError(ValueError):
    """The contact query is present but cannot be matched."""


def contains_text(value: str | None, needle: str) -> bool:
    return needle.casefold() in (value or "").casefold()


def name_tokens(value: str) -> list[str]:
    """Words in a name query. Commas and repeated spaces do not become tokens."""
    return [part for part in value.replace(",", " ").split() if part]


def person_name_matches(first_name: str | None, last_name: str | None, query: str) -> bool:
    """Every word must appear in the combined first and last name, in either order.

    "Sophia Price", "Price, Sophia", and "PRICE" all match Sophia Price. A single
    field can carry the whole name, so the search does not require both columns
    to contain the entire typed string.
    """
    tokens = name_tokens(query)
    if not tokens:
        return True
    haystack = f"{first_name or ''} {last_name or ''}"
    return all(contains_text(haystack, token) for token in tokens)


def normalize_phone(value: str | None) -> str:
    """Digits only, with a leading US country code removed from an 11-digit number."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def clean_contact_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def require_phone_digits(value: str | None) -> str | None:
    phone = clean_contact_text(value)
    if phone is None:
        return None
    if not normalize_phone(phone):
        raise ContactSearchError("Phone number must include digits")
    return phone


def _like_pattern(value: str) -> str:
    escaped = value.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


def _stored_phone_digits():
    raw = func.regexp_replace(func.coalesce(SavedLead.phone, ""), "[^0-9]", "", "g")
    return case(
        (and_(func.length(raw) == 11, func.substr(raw, 1, 1) == "1"), func.substr(raw, 2, 10)),
        else_=raw,
    )


def _saved_name_clause(value: str):
    haystack = func.concat(func.coalesce(SavedLead.first_name, ""), " ", func.coalesce(SavedLead.last_name, ""))
    clause = None
    for token in name_tokens(value):
        part = haystack.ilike(_like_pattern(token), escape="!")
        clause = part if clause is None else and_(clause, part)
    return clause


def apply_saved_lead_filters(
    statement: Select,
    *,
    full_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    company_name: str | None = None,
    industry: str | None = None,
) -> Select:
    """Narrow a saved-lead query. Blank values are ignored. Phone is matched on digits."""
    full_name = clean_contact_text(full_name)
    first_name = clean_contact_text(first_name)
    last_name = clean_contact_text(last_name)
    email = clean_contact_text(email)
    phone = require_phone_digits(phone)
    company_name = clean_contact_text(company_name)
    industry = clean_contact_text(industry)

    for name_query in (full_name, first_name, last_name):
        if name_query and (clause := _saved_name_clause(name_query)) is not None:
            statement = statement.where(clause)
    if email:
        statement = statement.where(SavedLead.email.ilike(_like_pattern(email), escape="!"))
    if phone:
        statement = statement.where(_stored_phone_digits() == normalize_phone(phone))
    if company_name:
        statement = statement.where(SavedLead.company_name.ilike(_like_pattern(company_name), escape="!"))
    if industry:
        statement = statement.where(SavedLead.industry.ilike(_like_pattern(industry), escape="!"))
    return statement
