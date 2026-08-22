"""Create the Sensor Type framework.

Revision ID: 20260822_0003
Revises: 20260822_0002
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260822_0003"
down_revision: str | None = "20260822_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

interface_type = postgresql.ENUM("GPIO", "ADC", "I2C", "ONE_WIRE", name="sensor_interface_type", create_type=False)
value_type = postgresql.ENUM("NUMERIC", "BOOLEAN", "TEXT", name="measurement_value_type", create_type=False)


def upgrade() -> None:
    interface_type.create(op.get_bind(), checkfirst=True)
    value_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "sensor_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("manufacturer", sa.String(200), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("interface_type", interface_type, nullable=False),
        sa.Column("driver_key", sa.String(100), nullable=False),
        sa.Column("configuration_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id", name="pk_sensor_types"),
        sa.UniqueConstraint("code", name="uq_sensor_types_code"),
        sa.UniqueConstraint("driver_key", name="uq_sensor_types_driver_key"),
    )
    for column in ("name", "interface_type", "is_active"):
        op.create_index(f"ix_sensor_types_{column}", "sensor_types", [column])
    op.create_table(
        "measurement_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sensor_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("value_type", value_type, nullable=False),
        sa.Column("default_unit", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["sensor_type_id"], ["sensor_types.id"], name="fk_measurement_definitions_sensor_type_id_sensor_types", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_measurement_definitions"),
        sa.UniqueConstraint("sensor_type_id", "key", name="uq_measurement_definitions_sensor_type_id_key"),
    )
    op.create_index("ix_measurement_definitions_sensor_type_id", "measurement_definitions", ["sensor_type_id"])


def downgrade() -> None:
    op.drop_table("measurement_definitions")
    op.drop_table("sensor_types")
    value_type.drop(op.get_bind(), checkfirst=True)
    interface_type.drop(op.get_bind(), checkfirst=True)
