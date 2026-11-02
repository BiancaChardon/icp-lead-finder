from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="backend")


@router.get("/health/ready", response_model=ReadinessResponse)
@router.get("/api/health/ready", response_model=ReadinessResponse)
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        body = ReadinessResponse(status="unavailable", database="unavailable")
        return JSONResponse(status_code=503, content=body.model_dump())
    return JSONResponse(content=ReadinessResponse(status="ok", database="ok").model_dump())
