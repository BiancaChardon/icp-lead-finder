from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.db import get_db
from app.deps import require_admin
from app.models import AuthSession, User
from app.schemas import CreateUserRequest, ResetPasswordRequest, UpdateUserRequest, UserOut
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> User:
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with that email already exists")

    user = User(email=email, full_name=body.full_name, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    record_event(
        db, "user_created", actor_user_id=admin.id, target_type="user", target_id=user.id,
        details={"role": user.role},
    )
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, body: UpdateUserRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> User:
    user = _get_user(db, user_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)

    if user.id == admin.id and (changes.get("role") == "member" or changes.get("is_active") is False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own administrator access or deactivate yourself",
        )

    for field, value in changes.items():
        setattr(user, field, value)
    if changes.get("is_active") is False:
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))

    record_event(
        db, "user_updated", actor_user_id=admin.id, target_type="user", target_id=user.id,
        details={"fields": sorted(changes)},
    )
    db.commit()
    return user


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int, body: ResetPasswordRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> Response:
    user = _get_user(db, user_id)
    user.password_hash = hash_password(body.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    record_event(db, "password_reset_by_admin", actor_user_id=admin.id, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
