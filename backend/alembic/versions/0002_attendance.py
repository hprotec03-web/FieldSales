"""salesman attendance (check-in / breaks / check-out with GPS)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# role name -> attendance permissions granted to existing companies' default roles
GRANTS = {
    "Administrator": ["Attendance.Mark", "Attendance.View"],
    "Manager": ["Attendance.Mark", "Attendance.View"],
    "Salesman": ["Attendance.Mark"],
}


def _loc(prefix: str, required: bool):
    return [
        sa.Column(f"{prefix}_lat", sa.Numeric(9, 6), nullable=not required),
        sa.Column(f"{prefix}_lng", sa.Numeric(9, 6), nullable=not required),
        sa.Column(f"{prefix}_accuracy", sa.Float()),
        sa.Column(f"{prefix}_address", sa.Unicode(300)),
        sa.Column(f"{prefix}_area", sa.Unicode(150)),
        sa.Column(f"{prefix}_mocked", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]


def upgrade() -> None:
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id")),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("tz_offset_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Unicode(20), nullable=False),
        sa.Column("check_in_at", sa.DateTime(), nullable=False),
        *_loc("check_in", True),
        sa.Column("check_in_note", sa.Unicode(500)),
        sa.Column("check_out_at", sa.DateTime()),
        *_loc("check_out", False),
        sa.Column("check_out_method", sa.Unicode(20)),
        sa.Column("check_out_note", sa.Unicode(500)),
        sa.Column("device_info", sa.Unicode(200)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_attendance_company_date", "attendance", ["company_id", "work_date"])
    op.create_index("ix_attendance_user_date", "attendance", ["user_id", "work_date"])
    op.create_index("uq_attendance_open_per_user", "attendance", ["user_id"], unique=True,
                    mssql_where=sa.text("status = 'Open'"), sqlite_where=sa.text("status = 'Open'"))

    op.create_table(
        "attendance_breaks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("attendance_id", sa.Integer(), sa.ForeignKey("attendance.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("break_type", sa.Unicode(30), nullable=False),
        sa.Column("note", sa.Unicode(500)),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        *_loc("start", True),
        sa.Column("end_at", sa.DateTime()),
        *_loc("end", False),
    )
    op.create_index("ix_attendance_breaks_company_id", "attendance_breaks", ["company_id"])
    op.create_index("ix_attendance_breaks_attendance_id", "attendance_breaks", ["attendance_id"])
    op.create_index("uq_attendance_break_open", "attendance_breaks", ["attendance_id"], unique=True,
                    mssql_where=sa.text("end_at IS NULL"), sqlite_where=sa.text("end_at IS NULL"))

    # New permissions, granted to the default roles of companies that already exist.
    conn = op.get_bind()
    perm_ids = {}
    for code in ("Attendance.Mark", "Attendance.View"):
        pid = conn.execute(sa.text("SELECT id FROM permissions WHERE code = :c"), {"c": code}).scalar()
        if pid is None:
            conn.execute(sa.text("INSERT INTO permissions (code) VALUES (:c)"), {"c": code})
            pid = conn.execute(sa.text("SELECT id FROM permissions WHERE code = :c"), {"c": code}).scalar()
        perm_ids[code] = pid
    for role_name, codes in GRANTS.items():
        role_ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM roles WHERE name = :n"), {"n": role_name})]
        for rid in role_ids:
            for code in codes:
                exists = conn.execute(sa.text("SELECT 1 FROM role_permissions WHERE role_id = :r AND permission_id = :p"),
                                      {"r": rid, "p": perm_ids[code]}).first()
                if not exists:
                    conn.execute(sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                                 {"r": rid, "p": perm_ids[code]})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code IN ('Attendance.Mark', 'Attendance.View'))"))
    conn.execute(sa.text("DELETE FROM permissions WHERE code IN ('Attendance.Mark', 'Attendance.View')"))
    op.drop_table("attendance_breaks")
    op.drop_table("attendance")
