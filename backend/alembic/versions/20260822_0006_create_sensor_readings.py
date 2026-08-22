"""Create typed Sensor Reading telemetry storage.

Revision ID: 20260822_0006
Revises: 20260822_0005
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260822_0006"
down_revision: str | None = "20260822_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

reading_quality = postgresql.ENUM(
    "GOOD", "UNCERTAIN", "BAD", name="reading_quality", create_type=False
)


def upgrade() -> None:
    reading_quality.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "sensor_readings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sensor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sensor_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reading_index", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("value_numeric", sa.Double(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("quality", reading_quality, nullable=False, server_default="GOOD"),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.CheckConstraint(
            "num_nonnulls(value_numeric, value_text, value_boolean) = 1",
            name="ck_sensor_readings_exactly_one_value",
        ),
        sa.CheckConstraint(
            "reading_index >= 0", name="ck_sensor_readings_reading_index_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name="fk_sensor_readings_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sensor_id"],
            ["sensors.id"],
            name="fk_sensor_readings_sensor_id_sensors",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sensor_channel_id"],
            ["sensor_channels.id"],
            name="fk_sensor_readings_sensor_channel_id_sensor_channels",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sensor_readings"),
        sa.UniqueConstraint(
            "device_id",
            "message_id",
            "reading_index",
            name="uq_sensor_readings_device_message_index",
        ),
    )
    op.create_index(
        "ix_sensor_readings_channel_recorded",
        "sensor_readings",
        ["sensor_channel_id", sa.text("recorded_at DESC")],
    )
    op.create_index(
        "ix_sensor_readings_sensor_recorded",
        "sensor_readings",
        ["sensor_id", sa.text("recorded_at DESC")],
    )
    op.create_index(
        "ix_sensor_readings_device_recorded",
        "sensor_readings",
        ["device_id", sa.text("recorded_at DESC")],
    )
    op.create_index(
        "ix_sensor_readings_recorded_at",
        "sensor_readings",
        [sa.text("recorded_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("sensor_readings")
    reading_quality.drop(op.get_bind(), checkfirst=True)
