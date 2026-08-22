from datetime import UTC

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User, UserRole
from tests.helpers import TEST_PASSWORD, create_test_user


def test_password_is_hashed() -> None:
    user = create_test_user()

    assert user.password_hash != TEST_PASSWORD
    assert user.password_hash.startswith("$argon2id$")


def test_duplicate_normalized_email_is_rejected() -> None:
    create_test_user(email="Case@Aqress.Dev")
    engine = create_engine(settings.database_url)
    with pytest.raises(IntegrityError), Session(engine) as session, session.begin():
        session.add(
            User(
                first_name="Duplicate",
                last_name="User",
                email="case@aqress.dev",
                password_hash="not-used",
                role=UserRole.USER,
            )
        )
    engine.dispose()


@pytest.mark.parametrize("role", list(UserRole))
def test_roles_and_timezone_aware_timestamps_are_persisted(role: UserRole) -> None:
    created = create_test_user(role=role)
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.id == created.id))
        assert user is not None
        assert user.role is role
        assert user.created_at.tzinfo is not None
        assert user.created_at.astimezone(UTC).utcoffset().total_seconds() == 0
        assert user.updated_at.tzinfo is not None
    engine.dispose()
