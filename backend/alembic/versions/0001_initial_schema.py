"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name, nullable=False):
    return sa.Column(name, sa.DateTime(), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Unicode(200), nullable=False),
        sa.Column("phone", sa.Unicode(50)), sa.Column("email", sa.Unicode(200)), sa.Column("address", sa.Unicode(500)),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _ts("created_at"), _ts("updated_at"),
        sa.UniqueConstraint("name", name="uq_companies_name"),
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.Unicode(200), nullable=False),
        sa.Column("city", sa.Unicode(100)), sa.Column("address", sa.Unicode(500)),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _ts("created_at"), _ts("updated_at"),
        sa.UniqueConstraint("company_id", "name", name="uq_branch_company_name"),
    )
    op.create_index("ix_branches_company_id", "branches", ["company_id"])
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.Unicode(100), nullable=False),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.Unicode(100), nullable=False),
        sa.Column("data_scope", sa.Unicode(20), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_role_company_name"),
    )
    op.create_index("ix_roles_company_id", "roles", ["company_id"])
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id"), primary_key=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id")),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("username", sa.Unicode(100), nullable=False),
        sa.Column("full_name", sa.Unicode(200), nullable=False),
        sa.Column("email", sa.Unicode(200)), sa.Column("mobile", sa.Unicode(50)),
        sa.Column("password_hash", sa.Unicode(255), nullable=False),
        sa.Column("status", sa.Unicode(20), nullable=False),
        _ts("created_at"), _ts("updated_at"),
        sa.UniqueConstraint("username", name="uq_user_username"),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.Unicode(64), primary_key=True),
        _ts("expires_at"),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.Unicode(200), nullable=False),
        sa.Column("mobile", sa.Unicode(30), nullable=False),
        sa.Column("business_type", sa.Unicode(100)), sa.Column("product", sa.Unicode(100)),
        sa.Column("contact_person", sa.Unicode(200)), sa.Column("contact_person_mobile", sa.Unicode(30)),
        sa.Column("address", sa.Unicode(500)),
        sa.Column("city", sa.Unicode(100), nullable=False),
        sa.Column("country", sa.Unicode(100), nullable=False),
        sa.Column("email", sa.Unicode(200)), sa.Column("location_url", sa.Unicode(500)),
        sa.Column("business_photo_url", sa.Unicode(500)),
        sa.Column("notes", sa.UnicodeText()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Unicode(20), nullable=False),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_customers_company_id", "customers", ["company_id"])
    op.create_index("ix_customers_company_mobile", "customers", ["company_id", "mobile"])
    op.create_index("ix_customers_company_name", "customers", ["company_id", "name"])
    op.create_table(
        "customer_salesmen",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("salesman_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        _ts("assigned_at"),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _ts("ended_at", nullable=True),
    )
    op.create_index("ix_customer_salesmen_company_id", "customer_salesmen", ["company_id"])
    op.create_index("ix_customer_salesmen_customer_id", "customer_salesmen", ["customer_id"])
    op.create_index("ix_assignment_salesman_active", "customer_salesmen", ["salesman_id", "is_active"])
    # Business rule: at most ONE active responsible salesman per customer (filtered unique index).
    op.create_index(
        "uq_customer_active_assignment", "customer_salesmen", ["customer_id"], unique=True,
        mssql_where=sa.text("is_active = 1"), sqlite_where=sa.text("is_active = 1"),
    )
    op.create_table(
        "visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id")),
        _ts("visit_time"),
        sa.Column("latitude", sa.Numeric(9, 6)), sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("purpose", sa.Unicode(300)), sa.Column("notes", sa.UnicodeText()),
        sa.Column("outcome", sa.Unicode(100)), sa.Column("photo_url", sa.Unicode(500)),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_visits_company_id", "visits", ["company_id"])
    op.create_index("ix_visits_customer_id", "visits", ["customer_id"])
    op.create_index("ix_visits_user_id", "visits", ["user_id"])
    op.create_index("ix_visits_company_time", "visits", ["company_id", "visit_time"])
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id")),
        sa.Column("title", sa.Unicode(300), nullable=False),
        sa.Column("notes", sa.UnicodeText()),
        _ts("due_date"),
        sa.Column("status", sa.Unicode(20), nullable=False),
        _ts("completed_at", nullable=True),
        _ts("created_at"), _ts("updated_at"),
    )
    op.create_index("ix_follow_ups_company_id", "follow_ups", ["company_id"])
    op.create_index("ix_follow_ups_customer_id", "follow_ups", ["customer_id"])
    op.create_index("ix_followups_company_status_due", "follow_ups", ["company_id", "status", "due_date"])
    op.create_table(
        "follow_up_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("follow_up_id", sa.Integer(), sa.ForeignKey("follow_ups.id"), nullable=False),
        sa.Column("outcome_text", sa.UnicodeText(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        _ts("recorded_at"),
        sa.Column("attachment_url", sa.Unicode(500)),
    )
    op.create_index("ix_follow_up_outcomes_company_id", "follow_up_outcomes", ["company_id"])
    op.create_index("ix_follow_up_outcomes_follow_up_id", "follow_up_outcomes", ["follow_up_id"])


def downgrade() -> None:
    for t in ("follow_up_outcomes", "follow_ups", "visits", "customer_salesmen", "customers", "revoked_tokens",
              "users", "role_permissions", "roles", "permissions", "branches", "companies"):
        op.drop_table(t)
