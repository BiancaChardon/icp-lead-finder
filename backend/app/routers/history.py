import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import SearchHistory, User
from app.schemas import HistoryOut, Page

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=Page[HistoryOut])
def list_history(
    page: int = Query(1, ge=1, le=10_000),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Page[HistoryOut]:
    owned = select(SearchHistory).where(SearchHistory.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(owned.subquery())) or 0
    rows = db.scalars(
        owned.order_by(SearchHistory.created_at.desc(), SearchHistory.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return Page[HistoryOut](
        items=[HistoryOut.model_validate(row) for row in rows],
        page=page,
        per_page=per_page,
        total=total,
        total_pages=max(1, math.ceil(total / per_page)),
    )


@router.get("/{history_id}", response_model=HistoryOut)
def get_history(
    history_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SearchHistory:
    entry = db.scalar(
        select(SearchHistory).where(SearchHistory.id == history_id, SearchHistory.user_id == user.id)
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return entry
