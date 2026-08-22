from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.models.user import User, UserRole
from app.scripts.seed_admin import AdminSeedData, seed_admin

SEED_DATA = AdminSeedData(
    email="Seed.Admin@Aqress.Dev",
    password="Local-Seed-Password-42",
    first_name="Seed",
    last_name="Administrator",
)


def test_admin_seed_succeeds() -> None:
    user, created = seed_admin(SEED_DATA)

    assert created is True
    assert user.email == "seed.admin@aqress.dev"
    assert user.role is UserRole.ADMIN
    assert verify_password(SEED_DATA.password, user.password_hash)


def test_admin_seed_is_idempotent() -> None:
    first, first_created = seed_admin(SEED_DATA)
    second, second_created = seed_admin(SEED_DATA)

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
    engine.dispose()
