import base64
import binascii
import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.reading import SensorReading
from app.models.sensor import Sensor, SensorChannel
from app.repositories.reading_repository import ReadingRepository
from app.schemas.telemetry import (
    LatestReadingsResponse,
    ReadingCursorResponse,
    ReadingResponse,
)


class ReadingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.readings = ReadingRepository(session)

    async def latest(self, sensor_id: uuid.UUID) -> LatestReadingsResponse:
        sensor = await self._sensor(sensor_id)
        items = await self.readings.latest_for_sensor(sensor_id)
        responses = [ReadingResponse.from_reading(item) for item in items]
        responses.sort(key=lambda item: item.name.casefold())
        return LatestReadingsResponse(
            sensor_id=sensor.id,
            sensor_uid=sensor.sensor_uid,
            readings=responses,
        )

    async def history(
        self,
        sensor_id: uuid.UUID,
        *,
        channel_id: uuid.UUID | None,
        from_at: datetime | None,
        to_at: datetime | None,
        limit: int,
        cursor: str | None,
    ) -> ReadingCursorResponse:
        await self._sensor(sensor_id)
        if channel_id is not None:
            exists = await self.session.scalar(
                select(SensorChannel.id).where(
                    SensorChannel.id == channel_id,
                    SensorChannel.sensor_id == sensor_id,
                )
            )
            if exists is None:
                raise AppError(
                    status_code=404,
                    code="CHANNEL_NOT_FOUND",
                    message="Sensor Channel was not found for this Sensor.",
                )
        self._validate_range(from_at, to_at)
        cursor_time, cursor_id = self._decode_cursor(cursor)
        rows = await self.readings.history(
            sensor_id=sensor_id,
            channel_id=channel_id,
            from_at=from_at,
            to_at=to_at,
            cursor_recorded_at=cursor_time,
            cursor_id=cursor_id,
            limit=limit,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = self._encode_cursor(page[-1]) if has_more and page else None
        return ReadingCursorResponse(
            items=[ReadingResponse.from_reading(item) for item in page],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def _sensor(self, sensor_id: uuid.UUID) -> Sensor:
        sensor = await self.session.scalar(select(Sensor).where(Sensor.id == sensor_id))
        if sensor is None:
            raise AppError(
                status_code=404,
                code="SENSOR_NOT_FOUND",
                message="Sensor was not found.",
            )
        return sensor

    @staticmethod
    def _validate_range(from_at: datetime | None, to_at: datetime | None) -> None:
        for value in (from_at, to_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise AppError(
                    status_code=422,
                    code="TIMEZONE_REQUIRED",
                    message="Reading time filters must include a timezone offset.",
                )
        if from_at is not None and to_at is not None and from_at > to_at:
            raise AppError(
                status_code=422,
                code="INVALID_TIME_RANGE",
                message="The from timestamp must be before or equal to the to timestamp.",
            )

    @staticmethod
    def _encode_cursor(item: SensorReading) -> str:
        payload = json.dumps(
            {"recorded_at": item.recorded_at.isoformat(), "id": str(item.id)},
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[datetime | None, uuid.UUID | None]:
        if cursor is None:
            return None, None
        try:
            padding = "=" * (-len(cursor) % 4)
            value = json.loads(base64.b64decode(cursor + padding, altchars=b"-_", validate=True))
            if not isinstance(value, dict) or set(value) != {"recorded_at", "id"}:
                raise ValueError
            recorded_at = datetime.fromisoformat(value["recorded_at"])
            if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
                raise ValueError
            return recorded_at, uuid.UUID(value["id"])
        except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
            raise AppError(
                status_code=400,
                code="INVALID_READING_CURSOR",
                message="The reading cursor is invalid.",
            ) from exc
