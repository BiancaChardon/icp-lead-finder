import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.excel_import import (
    MAX_UPLOAD_BYTES,
    ImportRejected,
    classify_preview,
    errors_csv,
    existing_record_ids,
    load_sheet,
    parse_mapping,
    save_rows,
)
from app.models import User
from app.rate_limit import client_ip, enforce_rate_limit
from app.routers.search import csv_response
from app.schemas import ImportPreview, ImportResult

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/leads/import", tags=["leads"])


def _rejected(exc: ImportRejected) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _overwrite(value: str | None) -> bool:
    if value is None or value.strip() == "":
        return False
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ImportRejected("Overwrite must be true or false.")


async def _read_limited(upload: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="The file exceeds the 10 MB limit.",
                )
            chunks.append(chunk)
    finally:
        await upload.close()
    return b"".join(chunks)


def _limit(request: Request, user: User) -> None:
    from app.config import Settings

    settings: Settings = request.app.state.settings
    key = f"import:user:{user.id}" if settings.auth_required else f"import:ip:{client_ip(request)}"
    enforce_rate_limit(request, key, 30)


@router.post("/preview", response_model=ImportPreview)
async def preview_import(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    mapping: str | None = Form(None),
) -> ImportPreview:
    _limit(request, user)
    payload = await _read_limited(file)
    try:
        parsed = load_sheet(file.filename, payload, parse_mapping(mapping))
        known = existing_record_ids(db, user, {row.provider_record_id for row in parsed.valid_rows})
        return classify_preview(parsed, known)
    except ImportRejected as exc:
        raise _rejected(exc) from None


@router.post("", response_model=ImportResult)
async def import_leads(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    mapping: str | None = Form(None),
    overwrite: str | None = Form(None),
) -> ImportResult:
    _limit(request, user)
    payload = await _read_limited(file)
    try:
        parsed = load_sheet(file.filename, payload, parse_mapping(mapping))
        return save_rows(db, user, parsed, overwrite=_overwrite(overwrite))
    except ImportRejected as exc:
        raise _rejected(exc) from None


@router.post("/errors")
async def import_error_report(
    request: Request,
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    mapping: str | None = Form(None),
) -> object:
    _limit(request, user)
    payload = await _read_limited(file)
    try:
        parsed = load_sheet(file.filename, payload, parse_mapping(mapping))
    except ImportRejected as exc:
        raise _rejected(exc) from None
    logger.info("Excel import error report rows=%s", len(parsed.invalid_rows))
    return csv_response(errors_csv(parsed), "import-errors")
