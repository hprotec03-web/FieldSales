import os
import tempfile
from types import SimpleNamespace

# Settings must be in place BEFORE the app is imported (get_settings is cached).
os.environ.update(
    DATABASE_URL="sqlite://", JWT_SECRET="test-secret-test-secret-test-secret-123", ENVIRONMENT="test",
    UPLOAD_DIR=tempfile.mkdtemp(prefix="fs-uploads-"), LOGIN_MAX_ATTEMPTS="5", DUPLICATE_RULE="mobile",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, login_limiter
from app.db.base import Base
from app.db.session import set_engine
from app.main import app
from app.models import Branch, Customer, CustomerSalesman, User
from app.services.org import create_company_with_roles

PASSWORD = "Passw0rd1"
_HASH = hash_password(PASSWORD)  # hash once; Argon2 is deliberately slow


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(eng, "connect")
    def _fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    set_engine(eng)
    login_limiter.reset()
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _user(db, company, roles, role, username, branch=None, status="Active"):
    u = User(company_id=company.id, role_id=roles[role].id, branch_id=branch.id if branch else None, username=username,
             full_name=username.replace("_", " ").title(), password_hash=_HASH, status=status)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def world(db):
    """Company A (admin, manager, 2 salesmen, branch) and Company B (admin, salesman, one customer)."""
    a, ra = create_company_with_roles(db, "Company A")
    b, rb = create_company_with_roles(db, "Company B")
    branch_a = Branch(company_id=a.id, name="HQ A", city="Dubai")
    branch_b = Branch(company_id=b.id, name="HQ B", city="Dubai")
    db.add_all([branch_a, branch_b])
    db.flush()
    w = SimpleNamespace(
        a=a, b=b, ra=ra, rb=rb, branch_a=branch_a, branch_b=branch_b,
        a_admin=_user(db, a, ra, "Administrator", "a_admin"),
        a_manager=_user(db, a, ra, "Manager", "a_manager"),
        a_sales1=_user(db, a, ra, "Salesman", "a_sales1"),
        a_sales2=_user(db, a, ra, "Salesman", "a_sales2"),
        b_admin=_user(db, b, rb, "Administrator", "b_admin"),
        b_sales=_user(db, b, rb, "Salesman", "b_sales"),
    )
    cb = Customer(company_id=b.id, name="B Customer", mobile="+971500000777", city="Dubai", country="United Arab Emirates",
                  created_by_user_id=w.b_sales.id, status="Active")
    db.add(cb)
    db.flush()
    db.add(CustomerSalesman(company_id=b.id, customer_id=cb.id, salesman_id=w.b_sales.id, assigned_by_user_id=w.b_admin.id, is_active=True))
    w.b_customer = cb
    db.commit()
    return w


def login(client, username, password=PASSWORD):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    # Login also sets the browser cookies on the shared TestClient; drop them so tests
    # authenticate only through the Bearer header and "anonymous" really is anonymous.
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def h(client, world):
    """Auth headers per user: h['a_manager']."""
    class Headers(dict):
        def __missing__(self, key):
            self[key] = login(client, key)
            return self[key]
    return Headers()


def new_customer(client, headers, name="Cust One", mobile="+971501111111", **kw):
    r = client.post("/api/v1/customers", json={"name": name, "mobile": mobile, "city": "Dubai", **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def assign(client, headers, customer_id, salesman_id):
    r = client.post(f"/api/v1/customers/{customer_id}/assignments", json={"salesman_id": salesman_id}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
