"""Demonstration provider.

Every record is generated, fictional, and flagged `is_demo=True`. Email
addresses use the reserved `.example` domain and phone numbers use the
reserved 555-01xx range, so none of them can reach a real person.
"""

import random
import re
from dataclasses import dataclass

from app.providers.base import ProspectPage, ProspectProvider, ProspectQuery
from app.schemas import Prospect, ProviderFilterInfo

DATA_SOURCE = "Demo data (mock provider)"
COMPANY_COUNT = 240
CONTACTS_PER_COMPANY = 4
RECORD_COUNT = COMPANY_COUNT * CONTACTS_PER_COMPANY
SEED = 20261102

INDUSTRIES = {
    "Healthcare": ["hospital", "clinics", "ehr", "telehealth", "patient care"],
    "Financial Services": ["banking", "payments", "lending", "wealth management"],
    "Manufacturing": ["industrial", "supply chain", "automation", "factory"],
    "Software": ["saas", "cloud", "devops", "platform"],
    "Education": ["university", "k-12", "edtech", "campus"],
    "Government Contracting": ["federal", "defense", "public sector", "compliance"],
    "Logistics": ["freight", "warehousing", "fleet", "distribution"],
    "Retail": ["ecommerce", "stores", "consumer", "omnichannel"],
}
SHARED_KEYWORDS = ["it infrastructure", "cybersecurity", "data center", "managed services", "automation"]

LOCATIONS = [
    ("Baltimore", "MD", "Maryland"),
    ("Bethesda", "MD", "Maryland"),
    ("Rockville", "MD", "Maryland"),
    ("Columbia", "MD", "Maryland"),
    ("Arlington", "VA", "Virginia"),
    ("Reston", "VA", "Virginia"),
    ("Richmond", "VA", "Virginia"),
    ("Washington", "DC", "District of Columbia"),
    ("Philadelphia", "PA", "Pennsylvania"),
    ("New York", "NY", "New York"),
    ("Raleigh", "NC", "North Carolina"),
    ("Atlanta", "GA", "Georgia"),
    ("Chicago", "IL", "Illinois"),
    ("Austin", "TX", "Texas"),
    ("Denver", "CO", "Colorado"),
    ("Seattle", "WA", "Washington"),
]
# Weighted toward the Maryland / Virginia / D.C. region so the demo reflects the team's core market.
LOCATION_WEIGHTS = [3 if state in ("MD", "VA", "DC") else 1 for _, state, _ in LOCATIONS]
AREA_CODES = {"MD": "410", "VA": "703", "DC": "202", "PA": "215", "NY": "212", "NC": "919",
              "GA": "404", "IL": "312", "TX": "512", "CO": "303", "WA": "206"}

TITLES = [
    "Chief Information Officer (CIO)",
    "Chief Technology Officer (CTO)",
    "IT Director",
    "VP of Information Technology",
    "Director of Infrastructure",
    "Chief Information Security Officer (CISO)",
    "IT Manager",
    "VP of Operations",
    "Chief Financial Officer (CFO)",
    "Head of Procurement",
]
FIRST_NAMES = ["Avery", "Jordan", "Morgan", "Riley", "Casey", "Taylor", "Quinn", "Reese", "Drew", "Skyler",
               "Harper", "Rowan", "Emerson", "Finley", "Sage", "Parker", "Dakota", "Hayden", "Kendall", "Logan"]
LAST_NAMES = ["Ashford", "Bramley", "Calloway", "Dunmore", "Ellery", "Fairbanks", "Garrison", "Holloway",
              "Ingram", "Jessup", "Kingsley", "Lockhart", "Merriweather", "Northcott", "Oakes", "Pemberton",
              "Quarles", "Radcliffe", "Stanton", "Thornbury"]
NAME_PARTS = ["Bluepine", "Cedarline", "Harborview", "Ironbridge", "Lakemont", "Northgate", "Oakridge",
              "Pinecrest", "Redwater", "Silverbrook", "Stonefield", "Westhaven", "Brightwell", "Clearpath"]
NAME_SUFFIX = {
    "Healthcare": ["Health", "Medical Group", "Health System", "Care Partners"],
    "Financial Services": ["Financial", "Capital", "Bancorp", "Credit Union"],
    "Manufacturing": ["Industries", "Manufacturing", "Fabrication", "Components"],
    "Software": ["Software", "Labs", "Systems", "Cloud"],
    "Education": ["University", "Academy", "College", "Learning"],
    "Government Contracting": ["Federal Solutions", "Defense Systems", "Public Services", "Government Group"],
    "Logistics": ["Logistics", "Freight", "Distribution", "Transport"],
    "Retail": ["Retail", "Outfitters", "Market", "Brands"],
}

SORT_FIELDS = ("company_name", "last_name", "job_title", "industry", "employee_count", "city", "state")


@dataclass(frozen=True)
class _Record:
    prospect: Prospect
    state_name: str
    keywords: tuple[str, ...]


def _tokens(text: str) -> list[str]:
    # Drop periods first so abbreviations like "D.C." match "DC".
    return re.findall(r"[a-z0-9]+", text.lower().replace(".", ""))


def _contains_phrase(haystack: list[str], phrase: str) -> bool:
    needle = _tokens(phrase)
    if not needle:
        return False
    n = len(needle)
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def _slug(text: str) -> str:
    return "-".join(_tokens(text))


def _generate(seed: int = SEED) -> list[_Record]:
    rng = random.Random(seed)
    industries = list(INDUSTRIES)
    records: list[_Record] = []
    companies: list[tuple[str, str, int, tuple[str, str, str], tuple[str, ...]]] = []

    for i in range(COMPANY_COUNT):
        industry = industries[i % len(industries)]
        name = f"{rng.choice(NAME_PARTS)} {rng.choice(NAME_SUFFIX[industry])}"
        if any(c[0] == name for c in companies):
            name = f"{name} {i}"
        employees = rng.choice([25, 60, 120, 180, 250, 400, 650, 900, 1500, 3200, 7800])
        location = rng.choices(LOCATIONS, weights=LOCATION_WEIGHTS)[0]
        keywords = tuple(rng.sample(INDUSTRIES[industry], 2) + rng.sample(SHARED_KEYWORDS, 2))
        companies.append((name, industry, employees, location, keywords))

    contacts = [
        (company, title)
        for company in companies
        for title in rng.sample(TITLES, CONTACTS_PER_COMPANY)
    ]
    for i, ((name, industry, employees, (city, state, state_name), keywords), title) in enumerate(contacts):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        domain = f"{_slug(name)}.example"

        roll = rng.random()
        if roll < 0.5:
            email, email_status = f"{first}.{last}@{domain}".lower(), "verified"
        elif roll < 0.8:
            email, email_status = f"{first[0]}{last}@{domain}".lower(), "unverified"
        else:
            email, email_status = None, "unavailable"

        roll = rng.random()
        if roll < 0.35:
            phone_status = "verified"
        elif roll < 0.6:
            phone_status = "unverified"
        else:
            phone_status = "unavailable"
        phone = (
            f"+1 {AREA_CODES[state]}-555-01{rng.randint(0, 99):02d}" if phone_status != "unavailable" else None
        )

        prospect = Prospect(
            provider="mock",
            provider_record_id=f"demo-{i + 1:04d}",
            is_demo=True,
            data_source=DATA_SOURCE,
            company_name=name,
            first_name=first,
            last_name=last,
            job_title=title,
            email=email,
            email_status=email_status,
            phone=phone,
            phone_status=phone_status,
            company_website=f"https://www.{domain}",
            industry=industry,
            employee_count=employees,
            city=city,
            state=state,
            country="United States",
        )
        records.append(_Record(prospect=prospect, state_name=state_name, keywords=keywords))
    return records


class MockProvider(ProspectProvider):
    name = "mock"
    display_name = "Demo data (mock provider)"
    is_demo = True
    sort_fields = SORT_FIELDS
    filters = (ProviderFilterInfo(key="verified_email_only", label="Only verified emails", type="boolean"),)

    def __init__(self) -> None:
        self._records = _generate()

    def search(self, query: ProspectQuery) -> ProspectPage:
        self.validate_query(query)
        matches = [r.prospect for r in self._records if self._matches(r, query)]

        if query.sort_by:
            key = query.sort_by
            present = [p for p in matches if getattr(p, key) is not None]
            missing = [p for p in matches if getattr(p, key) is None]
            present.sort(
                key=lambda p: (v.lower() if isinstance(v := getattr(p, key), str) else v),
                reverse=query.sort_dir == "desc",
            )
            matches = present + missing
        else:
            matches.sort(key=lambda p: ((p.company_name or "").lower(), (p.last_name or "").lower()))

        start = (query.page - 1) * query.per_page
        page_records = matches[start : start + query.per_page]
        return ProspectPage(
            records=page_records,
            page=query.page,
            per_page=query.per_page,
            total=len(matches),
            has_more=start + query.per_page < len(matches),
        )

    @staticmethod
    def _matches(record: _Record, query: ProspectQuery) -> bool:
        c = query.criteria
        p = record.prospect

        if c.industry and not _contains_phrase(_tokens(p.industry or ""), c.industry):
            return False
        if c.job_titles:
            title = _tokens(p.job_title or "")
            if not any(_contains_phrase(title, t) for t in c.job_titles):
                return False
        if c.locations:
            place = _tokens(f"{p.city} {p.state} {record.state_name} {p.country}")
            if not any(_contains_phrase(place, loc) for loc in c.locations):
                return False
        if c.employee_min and (p.employee_count or 0) < c.employee_min:
            return False
        if c.employee_max and (p.employee_count or 0) > c.employee_max:
            return False
        if c.keywords:
            haystack = _tokens(" ".join(record.keywords) + " " + (p.company_name or ""))
            if not any(_contains_phrase(haystack, k) for k in c.keywords):
                return False
        if c.company_name and c.company_name.lower() not in (p.company_name or "").lower():
            return False
        if c.provider_filters.get("verified_email_only") and p.email_status != "verified":
            return False
        return True
