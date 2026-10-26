"""Demo data seeding.   Usage (after `alembic upgrade head`):   python -m app.db.seed

Creates two companies (to demonstrate isolation), roles/permissions, users, branches, customers,
assignments, visits, follow-ups and outcome history. Safe to re-run: it skips if the demo company exists.
Demo password comes from SEED_PASSWORD (default below) - DO NOT use in production."""
import os
from datetime import timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_engine
from app.models import Branch, Company, Customer, CustomerSalesman, FollowUp, FollowUpOutcome, User, Visit
from app.services.org import create_company_with_roles
from sqlalchemy.orm import Session

DEMO_PASSWORD = os.environ.get("SEED_PASSWORD", "Demo@12345")


def _user(db, company, roles, role, username, full_name, branch=None):
    u = User(company_id=company.id, role_id=roles[role].id, branch_id=branch.id if branch else None, username=username,
             full_name=full_name, email=f"{username}@example.com", password_hash=hash_password(DEMO_PASSWORD), status="Active")
    db.add(u)
    db.flush()
    return u


def seed(db: Session) -> None:
    from app.utils.time import utcnow
    if db.scalars(select(Company).where(Company.name == "Demo Trading LLC")).first():
        print("Demo data already present - nothing to do.")
        return
    now = utcnow()

    # ----- Company A -----
    a, roles = create_company_with_roles(db, "Demo Trading LLC", email="info@demo-trading.example")
    dxb = Branch(company_id=a.id, name="Dubai HQ", city="Dubai")
    shj = Branch(company_id=a.id, name="Sharjah Branch", city="Sharjah")
    db.add_all([dxb, shj]); db.flush()
    admin = _user(db, a, roles, "Administrator", "admin", "Alice Admin", dxb)
    mgr = _user(db, a, roles, "Manager", "manager", "Mohammed Manager", dxb)
    s1 = _user(db, a, roles, "Salesman", "salesman1", "Sara Salesman", dxb)
    s2 = _user(db, a, roles, "Salesman", "salesman2", "Sami Salesman", shj)

    def cust(name, mobile, city, btype, creator):
        c = Customer(company_id=a.id, name=name, mobile=mobile, city=city, business_type=btype, product=btype,
                     country="United Arab Emirates", created_by_user_id=creator.id, status="Active")
        db.add(c); db.flush(); return c

    def assign(c, s, by):
        db.add(CustomerSalesman(company_id=a.id, customer_id=c.id, salesman_id=s.id, assigned_by_user_id=by.id,
                                assigned_at=now - timedelta(days=10), is_active=True))

    c1 = cust("Al Noor Restaurant", "+971500000001", "Dubai", "Restaurant", s1)
    c2 = cust("Star Gym", "+971500000002", "Dubai", "Gym", s1)
    c3 = cust("City Medical Centre", "+971500000003", "Sharjah", "Medical", s2)
    c4 = cust("Fresh Mart Super Market", "+971500000004", "Ajman", "Super Market", mgr)
    c5 = cust("Glow Saloon", "+971500000005", "Dubai", "Saloon", mgr)
    c6 = cust("Desert Tours", "+971500000006", "Abu Dhabi", "Tours", admin)  # left unassigned on purpose
    # c2 was created by salesman1 and then transferred to salesman2 -> salesman1 must no longer see it.
    db.add(CustomerSalesman(company_id=a.id, customer_id=c2.id, salesman_id=s1.id, assigned_by_user_id=mgr.id,
                            assigned_at=now - timedelta(days=20), ended_at=now - timedelta(days=8), is_active=False))
    for c, s in ((c1, s1), (c2, s2), (c3, s2), (c4, s1), (c5, s2)):
        assign(c, s, mgr)
    db.flush()

    v1 = Visit(company_id=a.id, customer_id=c1.id, user_id=s1.id, branch_id=dxb.id, visit_time=now - timedelta(days=3),
               purpose="Product demo", notes="Owner interested in POS", outcome="Interested")
    v2 = Visit(company_id=a.id, customer_id=c3.id, user_id=s2.id, visit_time=now - timedelta(hours=2),
               purpose="Introduction", outcome="Needs Follow-up", latitude=25.3463, longitude=55.4209)
    db.add_all([v1, v2]); db.flush()

    f1 = FollowUp(company_id=a.id, customer_id=c1.id, user_id=s1.id, visit_id=v1.id, title="Follow-up with Al Noor Restaurant",
                  due_date=now - timedelta(days=1), status="Pending")
    f2 = FollowUp(company_id=a.id, customer_id=c3.id, user_id=s2.id, visit_id=v2.id, title="Follow-up with City Medical Centre",
                  due_date=now + timedelta(days=2), status="Pending")
    db.add_all([f1, f2]); db.flush()
    for days, text in ((6, "Customer requested product details"), (4, "Product details sent"), (2, "Customer requested a demonstration")):
        db.add(FollowUpOutcome(company_id=a.id, follow_up_id=f1.id, outcome_text=text, recorded_by_user_id=s1.id,
                               recorded_at=now - timedelta(days=days)))

    # ----- Company B (isolation demo) -----
    b, roles_b = create_company_with_roles(db, "Other Company FZE")
    badmin = _user(db, b, roles_b, "Administrator", "admin_b", "Bob Admin")
    bs = _user(db, b, roles_b, "Salesman", "salesman_b", "Bella Salesman")
    cb = Customer(company_id=b.id, name="Other Co Customer", mobile="+971500000099", city="Dubai", country="United Arab Emirates",
                  created_by_user_id=bs.id, status="Active")
    db.add(cb); db.flush()
    db.add(CustomerSalesman(company_id=b.id, customer_id=cb.id, salesman_id=bs.id, assigned_by_user_id=badmin.id, is_active=True))
    db.commit()
    print("Seeded. Demo logins (password in SEED_PASSWORD, default 'Demo@12345'):")
    print("  admin / manager / salesman1 / salesman2   (Demo Trading LLC)")
    print("  admin_b / salesman_b                       (Other Company FZE)")


if __name__ == "__main__":
    get_engine()
    from app.db.session import _SessionLocal
    with _SessionLocal() as session:
        seed(session)
