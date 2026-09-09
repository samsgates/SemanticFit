#!/bin/sh
set -eu

python - <<'PY'
import os, time
from sqlalchemy import create_engine, text
url = os.environ.get('DATABASE_URL', 'postgresql+psycopg://semanticfit:semanticfit@postgres:5432/semanticfit')
for attempt in range(60):
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as c:
            c.execute(text('SELECT 1'))
        break
    except Exception as exc:
        if attempt == 59:
            raise
        print(f'Waiting for PostgreSQL ({attempt + 1}/60): {exc}')
        time.sleep(2)
PY

semanticfit-bootstrap
exec gunicorn --bind 0.0.0.0:5000 --workers "${GUNICORN_WORKERS:-1}" --threads "${GUNICORN_THREADS:-8}" --timeout "${GUNICORN_TIMEOUT:-180}" --access-logfile - --error-logfile - wsgi:app
