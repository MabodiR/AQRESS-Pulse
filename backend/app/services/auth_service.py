import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_token,
    decode_token,
    hash_refresh_token,
    utc_now,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self.users.get_by_email(email)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AppError(
                status_code=401,
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
            )
        token_pair = await self._issue_token_pair(user)
        await self.session.commit()
        return token_pair

    async def refresh(self, raw_refresh_token: str) -> TokenPair:
        user_id = self._decode_subject(
            raw_refresh_token, "refresh", verify_expiration=False
        )
        stored_token = await self.refresh_tokens.get_for_update(
            hash_refresh_token(raw_refresh_token)
        )
        now = utc_now()
        if stored_token is None:
            raise self._invalid_refresh_error()
        if stored_token.revoked_at is not None:
            raise AppError(
                status_code=401,
                code="REFRESH_TOKEN_REVOKED",
                message="Refresh token has been revoked.",
            )
        if stored_token.expires_at <= now:
            raise AppError(
                status_code=401,
                code="REFRESH_TOKEN_EXPIRED",
                message="Refresh token has expired.",
            )
        if stored_token.user_id != user_id:
            raise self._invalid_refresh_error()

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise self._invalid_refresh_error()

        await self.refresh_tokens.revoke(stored_token, now)
        token_pair = await self._issue_token_pair(user)
        await self.session.commit()
        return token_pair

    async def logout(self, raw_refresh_token: str) -> None:
        user_id = self._decode_subject(raw_refresh_token, "refresh")
        stored_token = await self.refresh_tokens.get_for_update(
            hash_refresh_token(raw_refresh_token)
        )
        if stored_token is None or stored_token.user_id != user_id:
            raise self._invalid_refresh_error()
        if stored_token.revoked_at is None:
            await self.refresh_tokens.revoke(stored_token, utc_now())
            await self.session.commit()

    async def get_user_from_access_token(self, access_token: str) -> User:
        user_id = self._decode_subject(access_token, "access")
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise self._invalid_access_error()
        return user

    async def _issue_token_pair(self, user: User) -> TokenPair:
        access_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        refresh_delta = timedelta(days=settings.jwt_refresh_token_expire_days)
        access_token, _ = create_token(
            subject=user.id, token_type="access", expires_delta=access_delta
        )
        refresh_token, refresh_expires_at = create_token(
            subject=user.id, token_type="refresh", expires_delta=refresh_delta
        )
        await self.refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=refresh_expires_at,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(access_delta.total_seconds()),
        )

    @staticmethod
    def _decode_subject(
        raw_token: str, expected_type: str, *, verify_expiration: bool = True
    ) -> uuid.UUID:
        try:
            payload = decode_token(  # type: ignore[arg-type]
                raw_token, expected_type, verify_expiration=verify_expiration
            )
            return uuid.UUID(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            if expected_type == "access":
                raise AuthService._invalid_access_error() from exc
            raise AuthService._invalid_refresh_error() from exc

    @staticmethod
    def _invalid_access_error() -> AppError:
        return AppError(
            status_code=401,
            code="INVALID_ACCESS_TOKEN",
            message="Access token is invalid or expired.",
        )

    @staticmethod
    def _invalid_refresh_error() -> AppError:
        return AppError(
            status_code=401,
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token is invalid.",
        )
