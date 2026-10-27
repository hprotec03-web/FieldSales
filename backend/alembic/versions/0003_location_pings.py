"""background location tracking (a GPS point every ~10 minutes during working hours)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "location_pings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("attendance_id", sa.Integer(), sa.ForeignKey("attendance.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("accuracy", sa.Float()),
        sa.Column("speed", sa.Float()),
        sa.Column("is_mocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.Unicode(20), nullable=False, server_default="background"),
        sa.UniqueConstraint("user_id", "recorded_at", name="uq_location_ping_user_time"),
    )
    op.create_index("ix_location_pings_company_id", "location_pings", ["company_id"])
    op.create_index("ix_location_pings_attendance_time", "location_pings", ["attendance_id", "recorded_at"])


def downgrade() -> None:
    op.drop_table("location_pings")
