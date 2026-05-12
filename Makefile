.PHONY: up down seed lint lint-fix test test-unit test-int test-evals run all

up:
	docker compose up -d

down:
	docker compose down

lint:
	.venv/bin/ruff check src/ tests/ lambdas/
	.venv/bin/ruff format --check src/ tests/ lambdas/

lint-fix:
	.venv/bin/ruff check --fix src/ tests/ lambdas/
	.venv/bin/ruff format src/ tests/ lambdas/

seed:
	python -m src.rag.ingest

test:
	.venv/bin/pytest tests/

test-unit:
	.venv/bin/pytest tests/unit/ lambdas/

test-int:
	.venv/bin/pytest tests/integration/

test-evals:
	.venv/bin/pytest tests/evals/ -v

run:
	uvicorn src.api.main:app --reload

all: up seed run
