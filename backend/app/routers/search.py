import logging
import math
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.audit import record_event
from app.config import Settings
from app.csv_export import prospects_to_csv
from app.db import get_db
from app.deps import get_current_user, get_settings_dep
from app.models import SearchHistory, User
from app.providers import (
    ProspectPage,
    ProspectProvider,
    ProspectQuery,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitedError,
    UnsupportedQueryError,
    get_provider,
)
from app.rate_limit import client_ip, enforce_rate_limit
from app.schemas import MAX_PAGE, ExportRequest, ProviderInfo, SearchRequest, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


def csv_response(content: str, prefix: str) -> Response:
    filename = f"{prefix}-{datetime.now(UTC):%Y%m%d-%H%M}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _run_search(provider: ProspectProvider, query: ProspectQuery) -> ProspectPage:
    # Log only the error type: provider messages can contain request URLs or credentials.
    try:
        return provider.search(query)
    except UnsupportedQueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderRateLimitedError as exc:
        logger.warning("Contact provider %s rate limited the request", provider.name)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The contact-data provider's rate limit was reached. Please wait and try again.",
        ) from exc
    except ProviderNotConfiguredError as exc:
        logger.error("Contact provider %s is not configured", provider.name)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The contact-data provider is not configured.",
        ) from exc
    except Exception as exc:
        kind = "provider error" if isinstance(exc, ProviderError) else "unexpected error"
        logger.error("Contact provider %s failed (%s: %s)", provider.name, kind, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The contact-data provider returned an error. Please try again later.",
        ) from exc


@router.get("/search/provider", response_model=ProviderInfo)
def provider_info(
    provider: ProspectProvider = Depends(get_provider), _: User = Depends(get_current_user)
) -> ProviderInfo:
    return provider.info()


@router.post("/search", response_model=SearchResponse)
def search(
    body: SearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: ProspectProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings_dep),
) -> SearchResponse:
    # Without sign-in everyone shares one user, so limit per client address instead.
    limit_key = f"search:user:{user.id}" if settings.auth_required else f"search:ip:{client_ip(request)}"
    enforce_rate_limit(request, limit_key, settings.search_rate_limit_per_minute)

    query = ProspectQuery(
        criteria=body.criteria,
        page=body.page,
        per_page=body.per_page,
        sort_by=body.sort_by,
        sort_dir=body.sort_dir,
    )
    result = _run_search(provider, query)

    search_id = None
    if body.page == 1 and body.record_history:
        entry = SearchHistory(
            user_id=user.id,
            provider=provider.name,
            criteria=body.criteria.model_dump(mode="json"),
            result_count=result.total,
        )
        db.add(entry)
        db.commit()
        search_id = entry.id

    total_pages = None
    if result.total is not None:
        total_pages = min(math.ceil(result.total / body.per_page), MAX_PAGE)

    return SearchResponse(
        provider=provider.name,
        is_demo=provider.is_demo,
        results=result.records,
        page=result.page,
        per_page=result.per_page,
        total=result.total,
        total_pages=total_pages,
        has_more=result.has_more and body.page < MAX_PAGE,
        search_id=search_id,
    )


@router.post("/export/csv")
def export_csv(body: ExportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    record_event(db, "results_exported", actor_user_id=user.id, details={"count": len(body.records)})
    db.commit()
    return csv_response(prospects_to_csv(body.records), "icp-leads")
