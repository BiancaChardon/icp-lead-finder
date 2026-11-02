from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.security import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

T = TypeVar("T")

ContactStatus = Literal["verified", "unverified", "unavailable", "unknown"]
Role = Literal["admin", "member"]

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Password = Annotated[str, StringConstraints(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]

MAX_LIST_ITEMS = 10
MAX_PAGE = 20
MAX_PER_PAGE = 50
MAX_EMPLOYEES = 10_000_000


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Auth & users -----------------------------------------------------------


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
    auth_required: bool = True


class ChangePasswordRequest(StrictModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: Password


class CreateUserRequest(StrictModel):
    email: EmailStr
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    password: Password
    role: Role = "member"


class UpdateUserRequest(StrictModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    role: Role | None = None
    is_active: bool | None = None


class ResetPasswordRequest(StrictModel):
    new_password: Password


# --- Search -------------------------------------------------------------------


class SearchCriteria(StrictModel):
    industry: ShortText | None = None
    job_titles: list[ShortText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    locations: list[ShortText] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    employee_min: int | None = Field(default=None, ge=1, le=MAX_EMPLOYEES)
    employee_max: int | None = Field(default=None, ge=1, le=MAX_EMPLOYEES)
    keywords: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]] = Field(
        default_factory=list, max_length=MAX_LIST_ITEMS
    )
    company_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    provider_filters: dict[str, bool | int | str] = Field(default_factory=dict, max_length=10)

    @field_validator("industry", "company_name", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("job_titles", "locations", "keywords", mode="before")
    @classmethod
    def _drop_blank_items(cls, value: Any) -> Any:
        if isinstance(value, list):
            seen: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    item = item.strip()
                    if not item or item.lower() in (s.lower() for s in seen if isinstance(s, str)):
                        continue
                seen.append(item)
            return seen
        return value

    @model_validator(mode="after")
    def _check(self) -> "SearchCriteria":
        if self.employee_min and self.employee_max and self.employee_min > self.employee_max:
            raise ValueError("employee_min must be less than or equal to employee_max")
        if not any(
            [
                self.industry,
                self.job_titles,
                self.locations,
                self.employee_min,
                self.employee_max,
                self.keywords,
                self.company_name,
            ]
        ):
            raise ValueError("Enter at least one search criterion")
        return self


class SearchRequest(StrictModel):
    criteria: SearchCriteria
    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    per_page: Literal[10, 25, 50] = 25
    sort_by: str | None = Field(default=None, max_length=50)
    sort_dir: Literal["asc", "desc"] = "asc"
    # False when re-running the same search with a different sort or page size.
    record_history: bool = True


class Prospect(StrictModel):
    """A single contact record. Fields the provider does not supply stay null."""

    provider: Annotated[str, StringConstraints(min_length=1, max_length=50)]
    provider_record_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    is_demo: bool
    data_source: Annotated[str, StringConstraints(min_length=1, max_length=100)]

    company_name: str | None = Field(default=None, max_length=200)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    job_title: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    email_status: ContactStatus = "unknown"
    phone: str | None = Field(default=None, max_length=50)
    phone_status: ContactStatus = "unknown"
    company_website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=100)
    employee_count: int | None = Field(default=None, ge=0, le=MAX_EMPLOYEES)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _missing_contact_is_unavailable(self) -> "Prospect":
        if not self.email:
            self.email, self.email_status = None, "unavailable"
        elif self.email_status == "unavailable":
            self.email_status = "unknown"
        if not self.phone:
            self.phone, self.phone_status = None, "unavailable"
        elif self.phone_status == "unavailable":
            self.phone_status = "unknown"
        return self


class ProviderFilterInfo(BaseModel):
    key: str
    label: str
    type: Literal["boolean"]


class ProviderInfo(BaseModel):
    name: str
    display_name: str
    is_demo: bool
    sort_fields: list[str]
    filters: list[ProviderFilterInfo]
    max_page: int = MAX_PAGE
    per_page_options: list[int] = [10, 25, 50]


class SearchResponse(BaseModel):
    provider: str
    is_demo: bool
    results: list[Prospect]
    page: int
    per_page: int
    total: int | None
    total_pages: int | None
    has_more: bool
    search_id: int | None


class ExportRequest(StrictModel):
    records: list[Prospect] = Field(min_length=1, max_length=1000)


# --- Leads & history ---------------------------------------------------------


class SaveLeadsRequest(StrictModel):
    leads: list[Prospect] = Field(min_length=1, max_length=100)


class SaveLeadsResponse(BaseModel):
    saved: int
    already_saved: int


class SavedLeadOut(Prospect):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: int
    created_at: datetime


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    per_page: int
    total: int
    total_pages: int


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    criteria: dict[str, Any]
    result_count: int | None
    created_at: datetime
