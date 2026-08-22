"""Create physical Sensors, Channels, and Configuration history.

Revision ID: 20260822_0004
Revises: 20260822_0003
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260822_0004"
down_revision: str | None = "20260822_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

sensor_status = postgresql.ENUM("REGISTERED", "DISABLED", "ERROR", name="sensor_status", create_type=False)
configuration_status = postgresql.ENUM("PENDING", "PUBLISHED", "APPLIED", "FAILED", "SUPERSEDED", name="sensor_configuration_status", create_type=False)


def upgrade() -> None:
    sensor_status.create(op.get_bind(), checkfirst=True)
    configuration_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "sensors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sensor_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sensor_uid", sa.String(128), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sensor_status, nullable=False, server_default="REGISTERED"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name="fk_sensors_device_id_devices", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sensor_type_id"], ["sensor_types.id"], name="fk_sensors_sensor_type_id_sensor_types", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_sensors"),
        sa.UniqueConstraint("device_id", "sensor_uid", name="uq_sensors_device_id_sensor_uid"),
    )
    for column in ("device_id", "sensor_type_id", "status", "enabled"):
        op.create_index(f"ix_sensors_{column}", "sensors", [column])
    op.create_table(
        "sensor_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sensor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("measurement_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"], name="fk_sensor_channels_sensor_id_sensors", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["measurement_definition_id"],
            ["measurement_definitions.id"],
            name="fk_sensor_channels_measurement_definition",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sensor_channels"),
        sa.UniqueConstraint("sensor_id", "measurement_definition_id", name="uq_sensor_channels_sensor_id_measurement_definition_id"),
    )
    op.create_index("ix_sensor_channels_sensor_id", "sensor_channels", ["sensor_id"])
    op.create_index("ix_sensor_channels_measurement_definition_id", "sensor_channels", ["measurement_definition_id"])
    op.create_table(
        "sensor_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sensor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", configuration_status, nullable=False, server_default="PENDING"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"], name="fk_sensor_configurations_sensor_id_sensors", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_sensor_configurations"),
        sa.UniqueConstraint("sensor_id", "config_version", name="uq_sensor_configurations_sensor_id_config_version"),
    )
    op.create_index("ix_sensor_configurations_sensor_id", "sensor_configurations", ["sensor_id"])
    op.create_index("uq_sensor_configurations_current", "sensor_configurations", ["sensor_id"], unique=True, postgresql_where=sa.text("is_current"))


def downgrade() -> None:
    op.drop_table("sensor_configurations")
    op.drop_table("sensor_channels")
    op.drop_table("sensors")
    configuration_status.drop(op.get_bind(), checkfirst=True)
    sensor_status.drop(op.get_bind(), checkfirst=True)
