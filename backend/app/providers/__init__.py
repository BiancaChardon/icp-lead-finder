from fastapi import Request

from app.providers.base import (
    ProspectPage,
    ProspectProvider,
    ProspectQuery,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitedError,
    UnsupportedQueryError,
)
from app.providers.mock import MockProvider

__all__ = [
    "ProspectPage",
    "ProspectProvider",
    "ProspectQuery",
    "ProviderError",
    "ProviderNotConfiguredError",
    "ProviderRateLimitedError",
    "UnsupportedQueryError",
    "build_provider",
    "get_provider",
]


def build_provider(name: str) -> ProspectProvider:
    if name == "mock":
        return MockProvider()
    # Real providers (e.g. Apollo.io) are registered here once implemented and
    # tested; see docs/PROVIDERS.md.
    raise ProviderNotConfiguredError(f"Unknown contact provider '{name}'")


def get_provider(request: Request) -> ProspectProvider:
    return request.app.state.provider
