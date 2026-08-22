from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AppError(
            status_code=401,
            code="AUTHENTICATION_REQUIRED",
            message="A valid access token is required.",
        )
    return await AuthService(session).get_user_from_access_token(credentials.credentials)


async def require_writer(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role == UserRole.VIEWER:
        raise AppError(status_code=403, code="FORBIDDEN", message="Your role does not allow this action.")
    return user


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.ADMIN:
        raise AppError(status_code=403, code="FORBIDDEN", message="Administrator access is required.")
    return user
