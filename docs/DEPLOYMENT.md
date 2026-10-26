# Deployment guide

> Do not call this production-ready until the full test-suite (SQLite + SQL Server integration), a security review and acceptance testing have passed in *your* environment. They have not been run yet (see `CHECKLIST.md`).

## 1. SQL Server
* SQL Server 2019+ (existing installation is fine; no container is required).
* Create a database and a dedicated login/user (`CREATE LOGIN fieldsales_app ...; CREATE USER ...`). For `alembic upgrade head` the user needs DDL rights (`db_owner` or `db_ddladmin`); for day-to-day running you may reduce to `db_datareader/db_datawriter` and run migrations with a separate deployment account.
* Use a CI collation (default `SQL_Latin1_General_CP1_CI_AS` is fine; all text columns are `NVARCHAR`, so Arabic/Unicode is supported).
* Enable TLS on the server and set `DB_TRUST_SERVER_CERTIFICATE=false` in production once a valid certificate is installed.

## 2. Backend
1. Install the ODBC Driver 18 (see README) or use the provided `backend/Dockerfile` (installs it for you).
2. Copy `backend/.env.example` -> `.env`. In production set `ENVIRONMENT=production`, a random `JWT_SECRET` (>=32 chars; the app refuses to start otherwise), `COOKIE_SECURE=true`, `CORS_ORIGINS=https://your-web-host` (only needed if web and API are on different origins).
3. `alembic upgrade head`, then start: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers` behind a TLS reverse proxy. For multiple workers use `gunicorn -k uvicorn.workers.UvicornWorker -w 4 app.main:app`.
4. **Login rate limiting is in-process memory.** With several workers/instances, also rate-limit `/api/v1/auth/login` at the proxy/WAF (or replace `LoginRateLimiter` with a Redis-backed one).
5. Do **not** run `python -m app.db.seed` in production (demo passwords).

## 3. Web
`cd web && npm ci && npm run build` -> serve `web/dist` from nginx (see `web/nginx.conf`, which also reverse-proxies `/api/` to the API so the HttpOnly cookie stays same-origin). Or `docker compose up --build` (API on :8000, web on :8080).

## 4. HTTPS
Terminate TLS at nginx/IIS ARR/Caddy/a cloud load balancer (e.g. Let's Encrypt via certbot or Caddy). Forward `X-Forwarded-Proto`; keep `COOKIE_SECURE=true`. Add HSTS at the proxy. Mobile release builds require HTTPS.

## 5. Secrets
Keep `.env`/secrets out of git (`.gitignore` already excludes `.env`). In production use your platform's secret store (Docker/Kubernetes secrets, Azure Key Vault, AWS Secrets Manager, Windows service environment variables). Rotating `JWT_SECRET` signs everyone out. Argon2id hashes are self-describing, so hash parameters can be raised later without migrations.

## 6. Files
Uploads go to `UPLOAD_DIR` (Docker: the `uploads` volume). Keep it outside any web-served or executable directory; it is only reachable through the authenticated `/api/v1/files/...` endpoint. Back it up together with the database. To use S3/Azure Blob implement `Storage` (`app/services/storage.py`) and return it from `get_storage()`; the serving endpoint would then stream from the object store.

## 7. Backups & logging
* Database: full backup nightly + log backups if you need point-in-time recovery (`BACKUP DATABASE FieldSales TO DISK=...` or your backup tool); test restores regularly. Retain revoked-token rows no longer than their expiry (the app prunes them on logout).
* Logs go to stdout (captured by Docker/systemd). Passwords, tokens and SQL parameters are never logged; unexpected errors log a stack trace server-side but return a generic 500 to clients.
* Health: `GET /health` (liveness), `GET /health/db` (readiness incl. SQL Server).

## 8. Mobile
* **Android:** install Android Studio + SDK, `flutter doctor --android-licenses`, create an upload keystore, configure `android/key.properties`, then `flutter build appbundle --release --dart-define=API_BASE_URL=https://...`.
* **iOS:** macOS + Xcode + Apple Developer account; `flutter build ipa --release --dart-define=API_BASE_URL=https://...`, then upload via Xcode/Transporter. No store submission has been performed.
