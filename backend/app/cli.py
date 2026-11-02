"""Server-side administration commands.

Run inside the backend container, for example:
    docker compose exec backend python -m app.cli create-admin --email you@company.com --name "Your Name"
"""

import argparse
import getpass
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import record_event
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models import AuthSession, User
from app.security import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH, hash_password


class CliError(Exception):
    pass


def _normalize_email(raw: str) -> str:
    try:
        return validate_email(raw, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise CliError(f"Invalid email address: {exc}") from exc


def _check_password(password: str) -> str:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise CliError(f"Password must be {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} characters")
    return password


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return _check_password(sys.stdin.readline().rstrip("\n"))
    first = getpass.getpass("Password: ")
    if getpass.getpass("Confirm password: ") != first:
        raise CliError("Passwords do not match")
    return _check_password(first)


def create_admin(db: Session, email: str, name: str, password: str) -> User:
    email = _normalize_email(email)
    if not name.strip():
        raise CliError("Name is required")
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise CliError(f"A user with email {email} already exists")
    user = User(email=email, full_name=name.strip(), password_hash=hash_password(_check_password(password)),
                role="admin")
    db.add(user)
    db.flush()
    record_event(db, "admin_created_via_cli", target_type="user", target_id=user.id)
    db.commit()
    return user


def reset_password(db: Session, email: str, password: str) -> User:
    email = _normalize_email(email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise CliError(f"No user with email {email}")
    user.password_hash = hash_password(_check_password(password))
    user.is_active = True
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    record_event(db, "password_reset_via_cli", target_type="user", target_id=user.id)
    db.commit()
    return user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="ICP Lead Finder administration")
    sub = parser.add_subparsers(dest="command", required=True)

    p_admin = sub.add_parser("create-admin", help="Create an administrator account")
    p_admin.add_argument("--email", required=True)
    p_admin.add_argument("--name", required=True)
    p_admin.add_argument("--password-stdin", action="store_true", help="Read the password from standard input")

    p_reset = sub.add_parser("reset-password", help="Reset a user's password and re-activate the account")
    p_reset.add_argument("--email", required=True)
    p_reset.add_argument("--password-stdin", action="store_true", help="Read the password from standard input")

    args = parser.parse_args(argv)
    engine = make_engine(get_settings().database_url)
    try:
        with make_session_factory(engine)() as db:
            password = _read_password(args.password_stdin)
            if args.command == "create-admin":
                user = create_admin(db, args.email, args.name, password)
                print(f"Created administrator {user.email}")
            else:
                user = reset_password(db, args.email, password)
                print(f"Password reset for {user.email}")
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
