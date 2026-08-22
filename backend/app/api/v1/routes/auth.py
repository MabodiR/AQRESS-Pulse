from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    pair = await AuthService(session).login(payload.email, payload.password)
    return TokenResponse(**pair.__dict__)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    pair = await AuthService(session).refresh(payload.refresh_token)
    return TokenResponse(**pair.__dict__)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    payload: LogoutRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogoutResponse:
    await AuthService(session).logout(payload.refresh_token)
    return LogoutResponse()


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user

