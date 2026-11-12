"""One-time operator-run bootstrap for the initial Sentinel accounts.

Run from the backend directory once per target PostgreSQL database with its
DATABASE_URL selected. The password variables are SEED_TOMMY_VERCETTI_PASSWORD,
SEED_KEN_ROSENBERG_PASSWORD, SEED_LANCE_VANCE_PASSWORD, and
SEED_SONNY_FORELLI_PASSWORD. Only accounts that must be created or converted
need a variable; these values are not needed by app runtime. Existing matching
accounts must already be approved; this command does not override approval.
"""

import os
from typing import List, Mapping, Optional, Tuple

from core.database import SessionLocal
from init_db import init_db
from models.user import User
from services.auth import hash_password
from sqlalchemy.orm import Session


LEGACY_ADMIN_EMAIL = "admin@sentinel.local"
ACCOUNT_DETAILS = (
    ("tommy.vercetti@example.com", "Tommy Vercetti", "admin", "SEED_TOMMY_VERCETTI_PASSWORD"),
    ("ken.rosenberg@example.com", "Ken Rosenberg", "public", "SEED_KEN_ROSENBERG_PASSWORD"),
    ("lance.vance@example.com", "Lance Vance", "public", "SEED_LANCE_VANCE_PASSWORD"),
    ("sonny.forelli@example.com", "Sonny Forelli", "public", "SEED_SONNY_FORELLI_PASSWORD"),
)


class SeedConflict(RuntimeError):
    pass


def _pending_seed_actions(
    db: Session,
) -> List[Tuple[str, str, str, Optional[User]]]:
    target_emails = [account[0] for account in ACCOUNT_DETAILS]
    existing_users = {
        user.email: user
        for user in db.query(User).filter(User.email.in_(target_emails)).all()
    }
    legacy_admin = db.query(User).filter(User.email == LEGACY_ADMIN_EMAIL).first()
    tommy_email, tommy_name, tommy_role, _tommy_env = ACCOUNT_DETAILS[0]
    existing_tommy = existing_users.get(tommy_email)

    if legacy_admin and existing_tommy and legacy_admin.id != existing_tommy.id:
        raise SeedConflict(f"Both the legacy admin and {tommy_email} already exist")

    if existing_tommy:
        if existing_tommy.display_name != tommy_name or existing_tommy.role != tommy_role:
            raise SeedConflict(f"Target email is occupied by an unrelated account: {tommy_email}")
    elif legacy_admin:
        existing_users[tommy_email] = legacy_admin

    actions = []
    for email, display_name, role, _env_name in ACCOUNT_DETAILS:
        user = existing_users.get(email)
        if user is None:
            actions.append((email, display_name, role, None))
        elif email == tommy_email and user.email == LEGACY_ADMIN_EMAIL:
            actions.append((email, display_name, role, user))
        elif user.display_name != display_name or user.role != role:
            raise SeedConflict(f"Target email is occupied by an unrelated account: {email}")
        elif not user.approved:
            raise SeedConflict(f"Target account is not approved: {email}")
    return actions


def seed_initial_users(db: Session, passwords: Mapping[str, str]) -> None:
    try:
        actions = _pending_seed_actions(db)
    except Exception:
        db.rollback()
        raise
    missing_passwords = [email for email, _name, _role, _user in actions if not passwords.get(email)]
    if missing_passwords:
        raise ValueError(f"Missing password for account: {', '.join(missing_passwords)}")

    try:
        for email, display_name, role, user in actions:
            password_hash = hash_password(passwords[email])
            if user is None:
                user = User(
                    email=email,
                    display_name=display_name,
                    password_hash=password_hash,
                    role=role,
                    approved=True,
                )
                db.add(user)
            else:
                user.email = email
                user.display_name = display_name
                user.password_hash = password_hash
                user.role = role
                user.approved = True
        db.commit()
    except Exception:
        db.rollback()
        raise


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        actions = _pending_seed_actions(db)
        passwords = {}
        for email, _display_name, _role, _user in actions:
            env_name = next(
                account[3] for account in ACCOUNT_DETAILS if account[0] == email
            )
            password = os.environ.get(env_name)
            if not password:
                raise RuntimeError(f"Missing required environment variable: {env_name}")
            passwords[email] = password

        seed_initial_users(db, passwords)
        print("Initial Sentinel accounts are ready.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
