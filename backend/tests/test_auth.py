from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, hash_refresh_token, utc_now
from app.models.refresh_token import RefreshToken
from tests.helpers import create_test_user, login


def test_successful_login_stores_only_refresh_token_hash(client: TestClient) -> None:
    create_test_user()

    payload = login(client)

    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["expires_in"] == settings.jwt_access_token_expire_minutes * 60
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        stored = session.scalar(select(RefreshToken))
        assert stored is not None
        assert stored.token_hash == hash_refresh_token(str(payload["refresh_token"]))
        assert stored.token_hash != payload["refresh_token"]
    engine.dispose()


def test_incorrect_password_uses_generic_error(client: TestClient) -> None:
    create_test_user()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@aqress.dev", "password": "incorrect"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_unknown_email_uses_generic_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@aqress.dev", "password": "incorrect"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_me_requires_access_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_me_returns_current_user_with_valid_access_token(client: TestClient) -> None:
    user = create_test_user()
    tokens = login(client)

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
    assert response.json()["email"] == user.email
    assert response.json()["role"] == "ADMIN"
    assert response.json()["created_at"].endswith("Z")


def test_invalid_access_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-token"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"


def test_expired_access_token_is_rejected(client: TestClient) -> None:
    user = create_test_user()
    expired_token, _ = create_token(
        subject=user.id, token_type="access", expires_delta=timedelta(seconds=-1)
    )

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"


def test_refresh_rotates_token_and_revokes_used_token(client: TestClient) -> None:
    create_test_user()
    original = login(client)

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )

    assert response.status_code == 200
    rotated = response.json()
    assert rotated["refresh_token"] != original["refresh_token"]
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        old = session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(str(original["refresh_token"]))
            )
        )
        assert old is not None
        assert old.revoked_at is not None
        assert session.scalar(select(RefreshToken).where(RefreshToken.revoked_at.is_(None)))
    engine.dispose()


def test_revoked_refresh_token_is_rejected(client: TestClient) -> None:
    create_test_user()
    original = login(client)
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    ).status_code == 200

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"


def test_expired_stored_refresh_token_is_rejected(client: TestClient) -> None:
    user = create_test_user()
    expired_token, expires_at = create_token(
        subject=user.id, token_type="refresh", expires_delta=timedelta(seconds=-1)
    )
    engine = create_engine(settings.database_url)
    with Session(engine) as session, session.begin():
        session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(expired_token),
                expires_at=expires_at,
                created_at=utc_now(),
            )
        )
    engine.dispose()

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": expired_token}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_EXPIRED"


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    create_test_user()
    tokens = login(client)

    response = client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "logged_out"}
    rejected = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert rejected.status_code == 401
    assert rejected.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        stored = session.scalar(select(RefreshToken))
        assert stored is not None and stored.revoked_at is not None
    engine.dispose()


def test_refresh_token_cannot_authenticate_me(client: TestClient) -> None:
    create_test_user()
    tokens = login(client)

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"


def test_access_token_cannot_be_used_as_refresh_token(client: TestClient) -> None:
    create_test_user()
    tokens = login(client)

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
