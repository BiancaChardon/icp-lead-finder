import math

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.csv_export import prospects_to_csv
from app.db import get_db
from app.deps import get_current_user
from app.models import SavedLead, User
from app.routers.search import csv_response
from app.schemas import Page, SavedLeadOut, SaveLeadsRequest, SaveLeadsResponse

router = APIRouter(prefix="/api/leads", tags=["leads"])

MAX_EXPORT_ROWS = 5000


@router.get("", response_model=Page[SavedLeadOut])
def list_leads(
    page: int = Query(1, ge=1, le=10_000),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Page[SavedLeadOut]:
    owned = select(SavedLead).where(SavedLead.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(owned.subquery())) or 0
    rows = db.scalars(
        owned.order_by(SavedLead.created_at.desc(), SavedLead.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return Page[SavedLeadOut](
        items=[SavedLeadOut.model_validate(row) for row in rows],
        page=page,
        per_page=per_page,
        total=total,
        total_pages=max(1, math.ceil(total / per_page)),
    )


@router.post("", response_model=SaveLeadsResponse)
def save_leads(
    body: SaveLeadsRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SaveLeadsResponse:
    keys = {(lead.provider, lead.provider_record_id) for lead in body.leads}
    rows = db.execute(
        select(SavedLead.provider, SavedLead.provider_record_id).where(
            SavedLead.user_id == user.id,
            SavedLead.provider_record_id.in_([record_id for _, record_id in keys]),
        )
    )
    existing = {(provider, record_id) for provider, record_id in rows}

    saved = 0
    seen: set[tuple[str, str]] = set()
    for lead in body.leads:
        key = (lead.provider, lead.provider_record_id)
        if key in existing or key in seen:
            continue
        seen.add(key)
        db.add(SavedLead(user_id=user.id, **lead.model_dump()))
        saved += 1

    if saved:
        record_event(db, "leads_saved", actor_user_id=user.id, details={"count": saved})
    db.commit()
    return SaveLeadsResponse(saved=saved, already_saved=len(body.leads) - saved)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    lead = db.scalar(select(SavedLead).where(SavedLead.id == lead_id, SavedLead.user_id == user.id))
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/export.csv")
def export_saved_leads(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    rows = db.scalars(
        select(SavedLead)
        .where(SavedLead.user_id == user.id)
        .order_by(SavedLead.created_at.desc())
        .limit(MAX_EXPORT_ROWS)
    )
    leads = [SavedLeadOut.model_validate(row) for row in rows]
    record_event(db, "saved_leads_exported", actor_user_id=user.id, details={"count": len(leads)})
    db.commit()
    return csv_response(prospects_to_csv(leads), "saved-leads")
