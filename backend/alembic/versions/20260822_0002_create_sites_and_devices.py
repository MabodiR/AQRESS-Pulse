"""Create sites and devices.

Revision ID: 20260822_0002
Revises: 20260822_0001
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260822_0002"
down_revision: str | None = "20260822_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

device_status = postgresql.ENUM("PROVISIONING", "ONLINE", "OFFLINE", "DISABLED", "ERROR", name="device_status", create_type=False)
connection_type = postgresql.ENUM("WIFI", "ETHERNET", "CELLULAR", "LORA", "OTHER", name="connection_type", create_type=False)


def upgrade() -> None:
    device_status.create(op.get_bind(), checkfirst=True)
    connection_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_sites_latitude_range"),
        sa.CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_sites_longitude_range"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_sites_created_by_user_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_sites"),
    )
    op.create_index("ix_sites_created_by_user_id", "sites", ["created_by_user_id"])
    op.create_index("ix_sites_name", "sites", ["name"])
    op.create_index("ix_sites_is_active", "sites", ["is_active"])
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_uid", sa.String(128), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("device_type", sa.String(100), nullable=False),
        sa.Column("manufacturer", sa.String(200), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("firmware_version", sa.String(100), nullable=True),
        sa.Column("connection_type", connection_type, nullable=False),
        sa.Column("status", device_status, nullable=False, server_default="PROVISIONING"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_devices_site_id_sites", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_devices"),
        sa.UniqueConstraint("device_uid", name="uq_devices_device_uid"),
    )
    for column in ("site_id", "status", "is_active", "last_seen_at"):
        op.create_index(f"ix_devices_{column}", "devices", [column])


def downgrade() -> None:
    op.drop_table("devices")
    op.drop_index("ix_sites_is_active", table_name="sites")
    op.drop_index("ix_sites_name", table_name="sites")
    op.drop_index("ix_sites_created_by_user_id", table_name="sites")
    op.drop_table("sites")
    connection_type.drop(op.get_bind(), checkfirst=True)
    device_status.drop(op.get_bind(), checkfirst=True)
