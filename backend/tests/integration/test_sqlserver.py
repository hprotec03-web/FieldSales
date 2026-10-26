"""Integration tests that need a REAL SQL Server (constraints, FKs, filtered unique index, transactions).

Run:   set MSSQL_TEST_URL=mssql+pyodbc://sa:Password@localhost:1433/FieldSales_Test?driver=ODBC+Driver+18+for+SQL+Server^&TrustServerCertificate=yes
       pytest tests/integration -m sqlserver
The target database must be empty/disposable: the tests run `alembic upgrade head` and drop everything afterwards."""
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = [pytest.mark.sqlserver, pytest.mark.skipif(not os.environ.get("MSSQL_TEST_URL"), reason="MSSQL_TEST_URL not set")]


@pytest.fixture(scope="module")
def mssql_engine():
    url = os.environ["MSSQL_TEST_URL"]
    os.environ["DATABASE_URL"] = url
    from app.core.config import get_settings
    get_settings.cache_clear()
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    yield eng
    command.downgrade(cfg, "base")
    eng.dispose()


@pytest.fixture
def s(mssql_engine):
    from app.models import Company
    with Session(mssql_engine) as session:
        yield session
        session.rollback()


def _base(session):
    from app.models import Customer, User
    from app.services.org import create_company_with_roles
    from app.core.security import hash_password
    import uuid
    tag = uuid.uuid4().hex[:8]
    company, roles = create_company_with_roles(session, f"Co {tag}")
    u = User(company_id=company.id, role_id=roles["Salesman"].id, username=f"u{tag}", full_name="U", password_hash=hash_password("Passw0rd1"))
    session.add(u)
    session.flush()
    c = Customer(company_id=company.id, name="C", mobile="+971500000000", city="Dubai", country="UAE", created_by_user_id=u.id)
    session.add(c)
    session.flush()
    return company, u, c


def test_only_one_active_assignment_per_customer(s):
    from app.models import CustomerSalesman
    company, u, c = _base(s)
    mk = lambda: CustomerSalesman(company_id=company.id, customer_id=c.id, salesman_id=u.id, assigned_by_user_id=u.id, is_active=True)
    s.add(mk()); s.flush()
    s.add(mk())
    with pytest.raises(IntegrityError):
        s.flush()


def test_inactive_assignments_are_unlimited(s):
    from app.models import CustomerSalesman
    company, u, c = _base(s)
    for _ in range(3):
        s.add(CustomerSalesman(company_id=company.id, customer_id=c.id, salesman_id=u.id, assigned_by_user_id=u.id, is_active=False))
    s.flush()


def test_foreign_keys_block_orphans_and_history_deletion(s):
    from app.models import FollowUp, Visit
    from app.utils.time import utcnow
    company, u, c = _base(s)
    s.add(Visit(company_id=company.id, customer_id=c.id, user_id=u.id)); s.flush()
    s.delete(c)
    with pytest.raises(IntegrityError):
        s.flush()  # a customer with visit history cannot be deleted
    s.rollback()
    s.add(FollowUp(company_id=1, customer_id=987654321, user_id=1, title="x", due_date=utcnow()))
    with pytest.raises(IntegrityError):
        s.flush()  # dangling customer reference


def test_unique_username_and_company_name(s):
    from app.models import User
    company, u, c = _base(s)
    s.add(User(company_id=company.id, role_id=u.role_id, username=u.username, full_name="Dup", password_hash="x"))
    with pytest.raises(IntegrityError):
        s.flush()


def test_transaction_rollback_leaves_no_partial_data(s):
    from sqlalchemy import func, select
    from app.models import Customer, Visit
    company, u, c = _base(s)
    s.commit()
    s.add(Visit(company_id=company.id, customer_id=c.id, user_id=u.id)); s.flush()
    s.rollback()
    assert s.scalar(select(func.count()).select_from(Visit).where(Visit.company_id == company.id)) == 0
