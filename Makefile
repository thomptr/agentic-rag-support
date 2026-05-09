.PHONY: up down seed lint lint-fix test test-unit test-int run all

up:
	docker compose up -d

down:
	docker compose down

lint:
	.venv/bin/ruff check src/ tests/
	.venv/bin/ruff format --check src/ tests/

lint-fix:
	.venv/bin/ruff check --fix src/ tests/
	.venv/bin/ruff format src/ tests/

seed:
	python -m src.rag.ingest

test:
	.venv/bin/pytest tests/

test-unit:
	.venv/bin/pytest tests/unit/

test-int:
	.venv/bin/pytest tests/integration/

run:
	uvicorn src.api.main:app --reload

all: up seed run
