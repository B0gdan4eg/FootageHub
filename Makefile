.PHONY: help install install-dev format lint type-check test test-cov clean pre-commit-install pre-commit-run

help:
	@echo "Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install          - Install production dependencies"
	@echo "  make install-dev      - Install development dependencies"
	@echo "  make format           - Format code with black and isort"
	@echo "  make lint             - Run flake8 linter"
	@echo "  make type-check       - Run mypy type checker"
	@echo "  make security         - Run bandit security checks"
	@echo "  make test             - Run tests"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make pre-commit-install - Install pre-commit hooks"
	@echo "  make pre-commit-run   - Run pre-commit on all files"
	@echo "  make clean            - Clean up generated files"
	@echo "  make check            - Run all checks (format, lint, type-check, security, test)"
	@echo ""
	@echo "Staging Environment:"
	@echo "  make staging-init     - Initialize staging (up + migrate + seed)"
	@echo "  make staging-up       - Start staging environment"
	@echo "  make staging-down     - Stop staging environment"
	@echo "  make staging-restart  - Restart staging environment"
	@echo "  make staging-rebuild  - Rebuild staging environment"
	@echo "  make staging-logs     - Show all staging logs"
	@echo "  make staging-ps       - Show staging containers status"
	@echo "  make staging-migrate  - Apply migrations to staging DB"
	@echo "  make staging-seed     - Seed staging DB with test data"
	@echo "  make staging-clean    - Remove staging containers and volumes"
	@echo ""
	@echo "Docker (Production):"
	@echo "  make docker-build     - Build Docker images"
	@echo "  make docker-up        - Start production environment"
	@echo "  make docker-down      - Stop production environment"
	@echo "  make docker-logs      - Show production logs"

install:
	pip install -r requirements/base.txt

install-dev:
	pip install -r requirements/dev.txt

format:
	@echo "Running isort..."
	isort shared/ media_bot/ ai_bot/ tests/
	@echo "Running black..."
	black shared/ media_bot/ ai_bot/ tests/

lint:
	@echo "Running flake8..."
	flake8 shared/ media_bot/ ai_bot/

type-check:
	@echo "Running mypy..."
	mypy shared/ media_bot/ ai_bot/ --config-file pyproject.toml

security:
	@echo "Running bandit security checks..."
	bandit -r shared/ media_bot/ ai_bot/ -c pyproject.toml

test:
	@echo "Running tests..."
	pytest tests/ -v

test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ -v --cov=shared --cov=media_bot --cov=ai_bot --cov-report=term-missing --cov-report=html

pre-commit-install:
	@echo "Installing pre-commit hooks..."
	pre-commit install

pre-commit-run:
	@echo "Running pre-commit on all files..."
	pre-commit run --all-files

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf dist/ 2>/dev/null || true
	rm -rf build/ 2>/dev/null || true
	@echo "Cleanup complete!"

check: format lint type-check security test
	@echo "All checks passed! ✅"

# Docker commands
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# Database migrations
migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migrate-create:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Staging environment commands
staging-up:
	@echo "Starting staging environment..."
	docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build

staging-down:
	@echo "Stopping staging environment..."
	docker compose -f docker-compose.staging.yml down

staging-restart:
	@echo "Restarting staging environment..."
	docker compose -f docker-compose.staging.yml restart

staging-logs:
	@echo "Showing staging logs (Ctrl+C to exit)..."
	docker compose -f docker-compose.staging.yml logs -f

staging-logs-media:
	@echo "Showing MediaBot staging logs..."
	docker compose -f docker-compose.staging.yml logs -f media-bot

staging-logs-ai:
	@echo "Showing AIBot staging logs..."
	docker compose -f docker-compose.staging.yml logs -f ai-bot

staging-logs-db:
	@echo "Showing PostgreSQL staging logs..."
	docker compose -f docker-compose.staging.yml logs -f postgres

staging-ps:
	@echo "Staging containers status:"
	docker compose -f docker-compose.staging.yml ps

staging-migrate:
	@echo "Applying migrations to staging database..."
	docker exec -it footagehub-staging-media-bot alembic upgrade head

staging-seed:
	@echo "Seeding staging database with test data..."
	docker exec -it footagehub-staging-media-bot python scripts/setup_staging_db.py

staging-shell-media:
	@echo "Opening shell in MediaBot staging container..."
	docker exec -it footagehub-staging-media-bot bash

staging-shell-ai:
	@echo "Opening shell in AIBot staging container..."
	docker exec -it footagehub-staging-ai-bot bash

staging-shell-db:
	@echo "Opening PostgreSQL shell in staging database..."
	docker exec -it footagehub-staging-db psql -U postgres -d footagehub_staging

staging-clean:
	@echo "WARNING: This will remove all staging containers and volumes!"
	@read -p "Are you sure? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker compose -f docker-compose.staging.yml down -v; \
		echo "Staging environment cleaned!"; \
	else \
		echo "Aborted."; \
	fi

staging-rebuild:
	@echo "Rebuilding staging environment..."
	docker compose -f docker-compose.staging.yml down
	docker compose -f docker-compose.staging.yml up -d --build

staging-init: staging-up staging-migrate staging-seed
	@echo "✅ Staging environment initialized!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Configure .env.staging with your bot tokens"
	@echo "  2. Run 'make staging-restart' to apply changes"
	@echo "  3. Follow STAGING_TEST_PLAN.md for testing"
