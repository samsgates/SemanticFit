.PHONY: setup up down logs backend frontend test lint ingest inspect validate evaluate verify clean

setup:
	cp -n .env.example .env || true
	python -m venv .venv
	. .venv/bin/activate && pip install -e './backend[ml,dev]'
	cd frontend && npm install

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

backend:
	cd backend && flask --app wsgi:app run --debug --port 5000

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -q
	cd frontend && npm test

lint:
	cd backend && ruff check .
	cd frontend && npm run build

inspect:
	cd backend && semanticfit-ingest inspect ../data/raw/meta_Amazon_Fashion.jsonl

validate:
	cd backend && semanticfit-ingest validate ../data/raw/meta_Amazon_Fashion.jsonl

ingest:
	cd backend && semanticfit-ingest ingest ../data/raw/meta_Amazon_Fashion.jsonl

verify:
	cd backend && semanticfit-ingest verify

evaluate:
	cd backend && semanticfit-eval run --dataset ../evaluation/datasets/core.jsonl

clean:
	docker compose down -v
	rm -rf reports/evaluation/* reports/ingestion/* data/errors/*
