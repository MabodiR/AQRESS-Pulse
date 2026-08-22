from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user_repository import normalize_email

TEST_PASSWORD = "Correct-Horse-Battery-Staple-42"


def create_test_user(
    *,
    email: str = "admin@aqress.dev",
    password: str = TEST_PASSWORD,
    role: UserRole = UserRole.ADMIN,
) -> User:
    engine = create_engine(settings.database_url)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        user = User(
            first_name="Test",
            last_name="Administrator",
            email=normalize_email(email),
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        session.add(user)
        session.flush()
        session.refresh(user)
    engine.dispose()
    return user


def login(client: object, email: str = "admin@aqress.dev") -> dict[str, object]:
    response = client.post(  # type: ignore[attr-defined]
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    return response.json()
