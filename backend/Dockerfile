FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ACCEPT_EULA=Y

# Microsoft ODBC Driver 18 for SQL Server (Debian 12). See README for other platforms.
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg2 ca-certificates unixodbc-dev gcc g++ \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update && apt-get install -y --no-install-recommends msodbcsql18 \
 && apt-get purge -y gcc g++ gnupg2 && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd -m appuser && mkdir -p /data/uploads && chown -R appuser /data /app
USER appuser
ENV UPLOAD_DIR=/data/uploads
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
# Run migrations separately (docker compose run --rm api alembic upgrade head); then start the API.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
