import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.models.reading import SensorReading
from app.models.sensor import SensorChannel

READING_LOAD = (
    selectinload(SensorReading.sensor_channel).selectinload(
        SensorChannel.measurement_definition
    ),
)


class TelemetryReadingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def insert_idempotently(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        statement = (
            insert(SensorReading)
            .values(rows)
            .on_conflict_do_nothing(
                constraint="uq_sensor_readings_device_message_index"
            )
            .returning(SensorReading.id)
        )
        return len(list(self.session.scalars(statement)))


class ReadingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest_for_sensor(self, sensor_id: uuid.UUID) -> list[SensorReading]:
        statement = (
            select(SensorReading)
            .join(SensorChannel)
            .options(*READING_LOAD)
            .where(
                SensorReading.sensor_id == sensor_id,
                SensorChannel.enabled.is_(True),
            )
            .distinct(SensorReading.sensor_channel_id)
            .order_by(
                SensorReading.sensor_channel_id,
                SensorReading.recorded_at.desc(),
                SensorReading.id.desc(),
            )
        )
        return list(await self.session.scalars(statement))

    async def history(
        self,
        *,
        sensor_id: uuid.UUID,
        channel_id: uuid.UUID | None,
        from_at: datetime | None,
        to_at: datetime | None,
        cursor_recorded_at: datetime | None,
        cursor_id: uuid.UUID | None,
        limit: int,
    ) -> list[SensorReading]:
        filters = [SensorReading.sensor_id == sensor_id]
        if channel_id is not None:
            filters.append(SensorReading.sensor_channel_id == channel_id)
        if from_at is not None:
            filters.append(SensorReading.recorded_at >= from_at)
        if to_at is not None:
            filters.append(SensorReading.recorded_at <= to_at)
        if cursor_recorded_at is not None and cursor_id is not None:
            filters.append(
                or_(
                    SensorReading.recorded_at < cursor_recorded_at,
                    and_(
                        SensorReading.recorded_at == cursor_recorded_at,
                        SensorReading.id < cursor_id,
                    ),
                )
            )
        statement: Select[tuple[SensorReading]] = (
            select(SensorReading)
            .options(*READING_LOAD)
            .where(*filters)
            .order_by(SensorReading.recorded_at.desc(), SensorReading.id.desc())
            .limit(limit + 1)
        )
        return list(await self.session.scalars(statement))
