from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user_repository import normalize_email


@dataclass(frozen=True)
class AdminSeedData:
    email: str
    password: str
    first_name: str
    last_name: str


def seed_admin(data: AdminSeedData, database_url: str | None = None) -> tuple[User, bool]:
    engine = create_engine(database_url or settings.database_url)
    normalized_email = normalize_email(data.email)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        existing = session.scalar(select(User).where(User.email == normalized_email))
        if existing is not None:
            return existing, False

        user = User(
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            email=normalized_email,
            password_hash=hash_password(data.password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(user)
        session.flush()
        session.refresh(user)
        return user, True


def main() -> None:
    if not settings.admin_email or not settings.admin_password:
        raise SystemExit(
            "AQRESS_PULSE_ADMIN_EMAIL and AQRESS_PULSE_ADMIN_PASSWORD must be set before seeding."
        )
    user, created = seed_admin(
        AdminSeedData(
            email=settings.admin_email,
            password=settings.admin_password,
            first_name=settings.admin_first_name,
            last_name=settings.admin_last_name,
        )
    )
    action = "created" if created else "already exists"
    print(f"Development admin {user.email} {action}.")


if __name__ == "__main__":
    main()
