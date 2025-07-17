.PHONY: help install install-dev test test-cov lint format type-check clean dev worker docker-build docker-up docker-down

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	poetry install --only=main

install-dev: ## Install all dependencies including development
	poetry install
	poetry run pre-commit install

validate: ## Validate development environment setup
	poetry run python scripts/validate-setup.py

test: ## Run tests
	poetry run pytest

test-cov: ## Run tests with coverage report
	poetry run pytest --cov=src/insight_engine --cov-report=html --cov-report=term

test-fast: ## Run tests in parallel (faster)
	poetry run pytest -n auto

lint: ## Run linting checks
	poetry run ruff check src tests
	poetry run black --check src tests
	poetry run isort --check-only src tests

format: ## Format code
	poetry run black src tests
	poetry run isort src tests
	poetry run ruff check --fix src tests

type-check: ## Run type checking
	poetry run mypy src tests

quality: ## Run all quality checks
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test-cov

clean: ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build

dev: ## Start development server
	poetry run uvicorn src.insight_engine.main:app --host 0.0.0.0 --port 8000 --reload

worker: ## Start ARQ worker
	poetry run arq src.insight_engine.worker.WorkerSettings

docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start services with Docker Compose
	docker-compose up -d

docker-down: ## Stop Docker Compose services
	docker-compose down

docker-logs: ## View Docker Compose logs
	docker-compose logs -f