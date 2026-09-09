FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY app ./app
COPY ingestion ./ingestion
COPY evaluation ./evaluation
COPY wsgi.py ./wsgi.py
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh && pip install --upgrade pip && pip install '.[ml]'

EXPOSE 5000
ENTRYPOINT ["./entrypoint.sh"]
