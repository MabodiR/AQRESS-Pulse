import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.telemetry import LatestReadingsResponse, ReadingCursorResponse
from app.services.reading_service import ReadingService

router = APIRouter(tags=["readings"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Reader = Annotated[User, Depends(get_current_user)]


@router.get("/sensors/{sensor_id}/latest", response_model=LatestReadingsResponse)
async def latest_sensor_readings(
    sensor_id: uuid.UUID, session: Session, _user: Reader
) -> LatestReadingsResponse:
    return await ReadingService(session).latest(sensor_id)


@router.get("/sensors/{sensor_id}/readings", response_model=ReadingCursorResponse)
async def sensor_readings(
    sensor_id: uuid.UUID,
    session: Session,
    _user: Reader,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    cursor: str | None = None,
) -> ReadingCursorResponse:
    return await ReadingService(session).history(
        sensor_id,
        channel_id=None,
        from_at=from_at,
        to_at=to_at,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/sensors/{sensor_id}/channels/{channel_id}/readings",
    response_model=ReadingCursorResponse,
)
async def channel_readings(
    sensor_id: uuid.UUID,
    channel_id: uuid.UUID,
    session: Session,
    _user: Reader,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    cursor: str | None = None,
) -> ReadingCursorResponse:
    return await ReadingService(session).history(
        sensor_id,
        channel_id=channel_id,
        from_at=from_at,
        to_at=to_at,
        limit=limit,
        cursor=cursor,
    )
