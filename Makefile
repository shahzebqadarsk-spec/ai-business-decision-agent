.DEFAULT_GOAL := help
BACKEND := backend
PY := $(BACKEND)/.venv/bin

.PHONY: help setup env up down logs migrate migration backend-dev frontend-dev test test-backend test-frontend lint typecheck fmt check

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "Created .env - edit the passwords before use")

setup: env ## Install backend (venv) and frontend dependencies
	cd $(BACKEND) && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
	cd frontend && npm ci

up: env ## Start the whole stack with Docker Compose
	docker compose up --build

down: ## Stop the Docker Compose stack
	docker compose down

logs: ## Tail Docker Compose logs
	docker compose logs -f

migrate: ## Apply database migrations (local backend)
	cd $(BACKEND) && .venv/bin/alembic upgrade head

migration: ## Autogenerate a migration: make migration m="describe change"
	cd $(BACKEND) && .venv/bin/alembic revision --autogenerate -m "$(m)"

backend-dev: ## Run the API with auto-reload on :8000 (local)
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend-dev: ## Run the Vite dev server on :5173 (local)
	cd frontend && npm run dev

test-backend: ## Backend tests (needs PostgreSQL for the DB tests)
	cd $(BACKEND) && .venv/bin/pytest

test-frontend: ## Frontend tests
	cd frontend && npm test

test: test-backend test-frontend ## All tests

# synthetic_data/generator has no pyproject.toml of its own and sits outside backend/,
# so ruff's own config discovery wouldn't find backend's settings for it - lint passes
# --config explicitly (same backend/pyproject.toml, applied to both trees).
lint: ## Lint backend (ruff) and frontend (eslint)
	cd $(BACKEND) && .venv/bin/ruff check --config pyproject.toml app tests ../synthetic_data/generator
	cd $(BACKEND) && .venv/bin/ruff format --config pyproject.toml --check app tests ../synthetic_data/generator
	cd frontend && npm run lint

generate-data: ## Regenerate the synthetic dataset (seed=42 by default; pass SEED=n OUT=dir to override)
	PYTHONPATH=synthetic_data $(PY)/python -m generator --seed $(or $(SEED),42) --output $(or $(OUT),synthetic_data/output)

typecheck: ## Type-check backend (mypy --strict) and frontend (tsc)
	cd $(BACKEND) && .venv/bin/mypy
	cd frontend && npm run typecheck

fmt: ## Auto-format backend code (and synthetic_data/generator)
	cd $(BACKEND) && .venv/bin/ruff check --config pyproject.toml --fix app tests ../synthetic_data/generator
	cd $(BACKEND) && .venv/bin/ruff format --config pyproject.toml app tests ../synthetic_data/generator

check: lint typecheck test ## Everything CI would run
