import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def utc_now() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(
    *,
    subject: uuid.UUID,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
) -> tuple[str, datetime]:
    issued_at = utc_now()
    expires_at = issued_at + expires_delta
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": issued_at,
        "exp": expires_at,
    }
    if token_type == "refresh":
        payload["jti"] = str(uuid.uuid4())
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(
    token: str,
    expected_type: Literal["access", "refresh"],
    *,
    verify_expiration: bool = True,
) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"verify_exp": verify_expiration},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload
