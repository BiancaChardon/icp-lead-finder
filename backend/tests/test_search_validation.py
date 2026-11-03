import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas import SearchCriteria, SearchRequest

VALID = {"industry": "Healthcare"}


def search(client: TestClient, criteria: dict, **extra) -> int:
    return client.post("/api/search", json={"criteria": criteria, **extra}).status_code


def test_criteria_trims_and_dedupes():
    criteria = SearchCriteria(
        industry="  Healthcare ",
        job_titles=["CIO", " cio ", "", "CTO"],
        locations=["  Maryland  "],
        company_name="   ",
    )

    assert criteria.industry == "Healthcare"
    assert criteria.job_titles == ["CIO", "CTO"]
    assert criteria.locations == ["Maryland"]
    assert criteria.company_name is None


def test_at_least_one_criterion_required():
    with pytest.raises(ValidationError, match="at least one search criterion"):
        SearchCriteria(industry="  ", job_titles=["  "])


@pytest.mark.parametrize(
    "criteria",
    [
        {},
        {"industry": "x" * 101},
        {"job_titles": [f"title {i}" for i in range(11)]},
        {"locations": ["x" * 101]},
        {"keywords": ["k" * 51]},
        {"employee_min": 0},
        {"employee_max": 20_000_000},
        {"employee_min": 1000, "employee_max": 100},
        {"company_name": "c" * 201},
        {"industry": "Healthcare", "unexpected_field": "x"},
        {"industry": "Healthcare", "provider_filters": {f"f{i}": True for i in range(11)}},
    ],
)
def test_invalid_criteria_rejected(member_client: TestClient, criteria):
    assert search(member_client, criteria) == 422


@pytest.mark.parametrize(
    "extra",
    [
        {"page": 0},
        {"page": 21},
        {"per_page": 500},
        {"per_page": 7},
        {"sort_dir": "sideways"},
        {"sort_by": "password_hash"},
    ],
)
def test_search_limits_enforced(member_client: TestClient, extra):
    assert search(member_client, VALID, **extra) == 422


def test_unsupported_provider_filter_rejected(member_client: TestClient):
    response = member_client.post(
        "/api/search", json={"criteria": {"industry": "Healthcare", "provider_filters": {"made_up": True}}}
    )

    assert response.status_code == 422
    assert "not supported" in response.json()["detail"]


def test_provider_filter_type_checked(member_client: TestClient):
    criteria = {"industry": "Healthcare", "provider_filters": {"verified_email_only": "yes"}}

    assert search(member_client, criteria) == 422


def test_contact_details_count_as_a_criterion():
    criteria = SearchCriteria(email="  Lang@Harbor.example ", first_name="  ")

    assert criteria.email == "Lang@Harbor.example"
    assert criteria.first_name is None
    assert criteria.phone is None


def test_contact_only_search_is_accepted(member_client: TestClient):
    assert search(member_client, {"email": "example"}) == 200
    assert search(member_client, {"first_name": "Avery", "last_name": "Lang"}) == 200


def test_phone_without_digits_is_rejected(member_client: TestClient):
    with pytest.raises(ValidationError, match="digits"):
        SearchCriteria(phone="call me")
    assert search(member_client, {"phone": "call me"}) == 422


def test_search_request_defaults():
    request = SearchRequest(criteria=SearchCriteria(**VALID))

    assert (request.page, request.per_page, request.sort_by, request.sort_dir) == (1, 25, None, "asc")
