import re

import pytest

from app.providers import ProspectQuery, UnsupportedQueryError
from app.providers.mock import RECORD_COUNT, MockProvider
from app.schemas import SearchCriteria


@pytest.fixture(scope="module")
def provider() -> MockProvider:
    return MockProvider()


def run(provider: MockProvider, page: int = 1, per_page: int = 50, sort_by=None, sort_dir="asc", **criteria):
    query = ProspectQuery(
        criteria=SearchCriteria(**criteria), page=page, per_page=per_page, sort_by=sort_by, sort_dir=sort_dir
    )
    return provider.search(query)


def all_results(provider: MockProvider, **criteria):
    query = ProspectQuery(criteria=SearchCriteria(**criteria), page=1, per_page=RECORD_COUNT)
    return provider.search(query).records


def test_every_record_is_marked_demo_and_uses_reserved_contact_details(provider: MockProvider):
    records = all_results(provider, employee_min=1)

    assert len(records) == RECORD_COUNT
    for r in records:
        assert r.is_demo is True
        assert r.provider == "mock"
        assert "demo" in r.data_source.lower()
        if r.email:
            assert r.email.endswith(".example")
        if r.phone:
            assert re.fullmatch(r"\+1 \d{3}-555-01\d{2}", r.phone)
        assert r.company_website and r.company_website.endswith(".example")


def test_missing_contact_details_are_unavailable_not_invented(provider: MockProvider):
    records = all_results(provider, employee_min=1)

    statuses = {r.email_status for r in records} | {r.phone_status for r in records}
    assert statuses <= {"verified", "unverified", "unavailable"}
    assert any(r.email is None for r in records)
    for r in records:
        assert (r.email is None) == (r.email_status == "unavailable")
        assert (r.phone is None) == (r.phone_status == "unavailable")


def test_results_are_deterministic():
    a = run(MockProvider(), industry="Healthcare").records
    b = run(MockProvider(), industry="Healthcare").records

    assert [r.model_dump() for r in a] == [r.model_dump() for r in b]


def test_example_icp_search(provider: MockProvider):
    records = all_results(
        provider,
        industry="Healthcare",
        job_titles=["CIO", "CTO", "IT Director"],
        locations=["Maryland", "Virginia", "Washington, D.C."],
        employee_min=100,
        employee_max=1000,
    )

    assert records, "the demo dataset should match the example ICP"
    for r in records:
        assert r.industry == "Healthcare"
        assert any(t in r.job_title for t in ("(CIO)", "(CTO)", "IT Director"))
        assert r.state in {"MD", "VA", "DC"}
        assert 100 <= r.employee_count <= 1000


@pytest.mark.parametrize(
    "location,state",
    [("MD", "MD"), ("maryland", "MD"), ("Washington DC", "DC"), ("Washington, D.C.", "DC"), ("D.C.", "DC")],
)
def test_location_matching(provider: MockProvider, location, state):
    records = all_results(provider, locations=[location])

    assert records and all(r.state == state for r in records)


def test_keyword_and_company_name_filters(provider: MockProvider):
    by_keyword = all_results(provider, keywords=["telehealth"])
    assert by_keyword and all(r.industry == "Healthcare" for r in by_keyword)

    name = by_keyword[0].company_name
    by_name = all_results(provider, company_name=name.lower())
    assert by_name and all(r.company_name == name for r in by_name)


def test_verified_email_filter(provider: MockProvider):
    records = all_results(provider, industry="Software", provider_filters={"verified_email_only": True})

    assert records and all(r.email_status == "verified" for r in records)


def test_pagination(provider: MockProvider):
    per_page = 50
    last_page = -(-RECORD_COUNT // per_page)
    first = run(provider, employee_min=1, per_page=per_page)
    second = run(provider, employee_min=1, page=2, per_page=per_page)
    last = run(provider, employee_min=1, page=last_page, per_page=per_page)

    assert first.total == RECORD_COUNT
    assert len(first.records) == per_page and first.has_more
    assert {r.provider_record_id for r in first.records}.isdisjoint(r.provider_record_id for r in second.records)
    assert len(last.records) == RECORD_COUNT - (last_page - 1) * per_page and not last.has_more


def test_sorting(provider: MockProvider):
    asc = run(provider, employee_min=1, sort_by="employee_count").records
    desc = run(provider, employee_min=1, sort_by="employee_count", sort_dir="desc").records

    assert [r.employee_count for r in asc] == sorted(r.employee_count for r in asc)
    assert desc[0].employee_count == max(r.employee_count for r in all_results(provider, employee_min=1))


def test_unsupported_sort_rejected(provider: MockProvider):
    with pytest.raises(UnsupportedQueryError):
        run(provider, industry="Healthcare", sort_by="email")
