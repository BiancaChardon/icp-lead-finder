from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from app.schemas import Prospect, ProviderFilterInfo, ProviderInfo, SearchCriteria


class ProviderError(Exception):
    """The provider failed. The message is for logs only and is never shown to users."""


class ProviderRateLimitedError(ProviderError):
    pass


class ProviderNotConfiguredError(ProviderError):
    pass


class UnsupportedQueryError(ValueError):
    """The query uses a sort field or filter this provider does not support."""


@dataclass(frozen=True)
class ProspectQuery:
    criteria: SearchCriteria
    page: int
    per_page: int
    sort_by: str | None = None
    sort_dir: Literal["asc", "desc"] = "asc"


@dataclass(frozen=True)
class ProspectPage:
    records: list[Prospect]
    page: int
    per_page: int
    total: int | None
    has_more: bool


class ProspectProvider(ABC):
    """Interface every contact-data provider implements.

    Implementations must only return data the provider actually supplied:
    leave unknown fields as None and report verification status only when the
    provider states it.
    """

    name: str
    display_name: str
    is_demo: bool = False
    sort_fields: tuple[str, ...] = ()
    filters: tuple[ProviderFilterInfo, ...] = ()

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            display_name=self.display_name,
            is_demo=self.is_demo,
            sort_fields=list(self.sort_fields),
            filters=list(self.filters),
        )

    def validate_query(self, query: ProspectQuery) -> None:
        if query.sort_by is not None and query.sort_by not in self.sort_fields:
            raise UnsupportedQueryError(f"Sorting by '{query.sort_by}' is not supported by this provider")
        allowed = {f.key: f for f in self.filters}
        for key, value in query.criteria.provider_filters.items():
            spec = allowed.get(key)
            if spec is None:
                raise UnsupportedQueryError(f"Filter '{key}' is not supported by this provider")
            if spec.type == "boolean" and not isinstance(value, bool):
                raise UnsupportedQueryError(f"Filter '{key}' must be true or false")

    @abstractmethod
    def search(self, query: ProspectQuery) -> ProspectPage: ...
