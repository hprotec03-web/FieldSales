# FieldSales - multi-company field sales tracking

Python (FastAPI) API + SQL Server, a React web app and a Flutter app for Android/iOS.
Salesmen record customer visits and schedule follow-ups; managers assign customers and supervise; every company's data is isolated.

```
FieldSales/
  backend/   FastAPI, SQLAlchemy 2, Alembic, pytest      (Python 3.12+)
  web/       React + TypeScript + Vite + Tailwind         (Node 20+)
  mobile/    Flutter app (Android + iOS)                  (Flutter 3.22+)
  docs/      API reference, deployment guide, checklist & known issues
  docker-compose.yml
```

> ## Verification status - please read
> This project was generated in a sandbox that **could not download packages** (PyPI/npm were blocked) and had no SQL Server or Flutter SDK.
> Therefore **nothing has been executed**: the backend test-suite, the web build/tests and the Flutter app have **not been run**, and nothing has been tried against SQL Server.
> What *was* done: syntax checks of all Python, an offline run of the Pydantic request-validation rules, and careful static review.
> Treat this as a complete, carefully written first drop that needs its first real build/test pass (`pytest`, `npm run build`, `flutter analyze`). See `docs/CHECKLIST.md`.

## 1. Backend quick start (Windows)

Prerequisites: Python 3.12+, a SQL Server instance (2019+; Express is fine) and the **Microsoft ODBC Driver 18 for SQL Server**.

| OS | ODBC driver |
|---|---|
| Windows | Install "ODBC Driver 18 for SQL Server" from Microsoft (msi). |
| Ubuntu/Debian | add Microsoft's apt repo, then `sudo ACCEPT_EULA=Y apt-get install msodbcsql18 unixodbc-dev` |
| macOS | `brew tap microsoft/mssql-release && brew install msodbcsql18 mssql-tools18` |

```bat
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env          &:: then edit DB_* and JWT_SECRET
```
Create an empty database (any name, e.g. `FieldSales`) and a login with `db_owner` on it, put the details in `.env`, then:

```bat
alembic upgrade head            &:: creates the schema from the migration (the app never auto-creates tables)
python -m app.db.seed           &:: optional: demo companies, users, customers, visits, follow-ups
uvicorn app.main:app --reload   &:: http://localhost:8000/docs (Swagger), /health, /health/db
```
Linux/macOS: `python3.12 -m venv .venv && source .venv/bin/activate`, `cp .env.example .env`, same commands.

Updating the database later: add a model change, `alembic revision --autogenerate -m "describe change"`, **review** the generated file, then `alembic upgrade head`.

### Tests
```bat
cd backend && pytest                                    &:: ~60 business-rule tests on in-memory SQLite (no SQL Server needed)
set MSSQL_TEST_URL=mssql+pyodbc://user:pass@host/FieldSales_Test?driver=ODBC+Driver+18+for+SQL+Server^&TrustServerCertificate=yes
pytest tests/integration -m sqlserver                   &:: FK / filtered-unique-index / rollback checks on REAL SQL Server (disposable DB!)
```
The SQLite suite covers authentication, company isolation, assignment visibility, visits, follow-ups, outcome history, reports and files. Database-specific guarantees (the filtered unique index that allows only one active assignment per customer, foreign keys, transactions) are re-checked by the SQL Server integration tests.

## 2. Web app
```bash
cd web
npm install
npm run dev          # http://localhost:5173 (proxies /api to http://localhost:8000)
npm run typecheck && npm test
npm run build        # static files in web/dist
```
The browser uses an **HttpOnly cookie** for the JWT plus a CSRF double-submit token (`fs_csrf` cookie -> `X-CSRF-Token` header). The dev proxy / nginx keep everything same-origin.

## 3. Mobile app
See `mobile/README.md` (run `tool/setup_platforms.sh|ps1` once to generate `android/` and `ios/`). iOS builds require macOS + Xcode.

## 4. Demo accounts (after `python -m app.db.seed`; password `Demo@12345`, override with `SEED_PASSWORD`)
| Company | Username | Role | Sees |
|---|---|---|---|
| Demo Trading LLC | `admin` | Administrator | everything in the company, user/role/branch/company management |
| Demo Trading LLC | `manager` | Manager | all customers, assigns/reassigns, reports |
| Demo Trading LLC | `salesman1` | Salesman | only customers currently assigned to them |
| Demo Trading LLC | `salesman2` | Salesman | same, different customers |
| Other Company FZE | `admin_b`, `salesman_b` | Admin / Salesman | a completely separate company (isolation demo) |

### Demonstration workflow
1. Sign in as `salesman1`: dashboard shows assigned customers, 1 overdue follow-up ("Al Noor Restaurant"). Open it - three dated outcomes are already in the history.
2. Add a fourth outcome ("Demo scheduled"). Earlier entries stay; each shows who/when.
3. **Record visit -> New customer** ("Test Cafe", mobile +971500000123). It is created, visited and assigned to `salesman1` in one transaction. Optionally set a follow-up date -> a Pending follow-up "Follow-up with Test Cafe" appears.
4. Sign out, sign in as `manager`: Customers -> *Test Cafe* -> **Reassign** to `salesman2`.
5. Back as `salesman1`: *Test Cafe* is gone from the list, and opening its URL/API id returns 404 (also for visits and follow-ups).
6. As `salesman2`: the customer and its follow-up (with the original outcome authors preserved) are visible.
7. As `manager`: Reports -> Visits (date filter) -> Download CSV; Dashboard shows per-salesman activity.
8. Sign in as `admin_b`: none of company A's data is visible anywhere.

## 5. Business rules (as implemented - change deliberately, with tests)
* **Visibility:** users whose role has `data_scope = assigned` (Salesman) see a customer, its visits and its follow-ups **only while they are the active assignee**. Creator != assignee: after a transfer the creator loses access. Managers/Admins (`data_scope = company`) see the whole company.
* **One active salesman per customer** - enforced by a service rule *and* a filtered unique index (`is_active = 1`). Assignment history is kept.
* **Salesman-created customers:** only through the visit workflow (`POST /visits` with `new_customer`); the customer is auto-assigned to the creating salesman. This does not grant `Customer.Create`/`Customer.Edit`.
* **Duplicate customers:** `DUPLICATE_RULE` = `mobile` (default) | `name_mobile` | `name` | `off`, always within one company; mobile numbers are normalised (spaces/dashes removed). **This default is a proposal - confirm the business rule.**
* **Follow-up statuses:** `Pending -> Completed | Cancelled`, `Cancelled -> Pending`; `Completed` is final. Outcomes can be added only while Pending. Outcomes are append-only (no update/delete endpoint) and always show the person who actually recorded them.
* **Follow-up ownership:** `follow_ups.user_id` = original creator; the *responsible* salesman is the customer's current assignee.
* **Users are never hard-deleted** (history references them): "delete" sets status `Inactive`. A user with active customer assignments cannot be deactivated until those are reassigned.
* **Roles are per company**; the Administrator role's permissions are locked; companies themselves are created by the seed/CLI (there is no platform super-admin in scope).
* Timestamps are stored as UTC and sent as ISO-8601 with `Z`.

See `docs/API.md`, `docs/DEPLOYMENT.md`, `docs/CHECKLIST.md`.
