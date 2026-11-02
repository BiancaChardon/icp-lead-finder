from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_event(
    db: Session,
    event_type: str,
    *,
    actor_user_id: int | None = None,
    target_type: str | None = None,
    target_id: int | str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Add an audit event to the session; the caller commits.

    Never put passwords, tokens, API keys, or contact details in `details`.
    """
    db.add(
        AuditEvent(
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details or {},
        )
    )
