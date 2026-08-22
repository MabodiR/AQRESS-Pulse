"""Create per-Device MQTT credential identities.

Revision ID: 20260822_0005
Revises: 20260822_0004
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260822_0005"
down_revision: str | None = "20260822_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_mqtt_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name="fk_device_mqtt_credentials_device", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_device_mqtt_credentials"),
        sa.UniqueConstraint("device_id", name="uq_device_mqtt_credentials_device_id"),
        sa.UniqueConstraint("username", name="uq_device_mqtt_credentials_username"),
    )
    op.create_index("ix_device_mqtt_credentials_is_active", "device_mqtt_credentials", ["is_active"])


def downgrade() -> None:
    op.drop_table("device_mqtt_credentials")
