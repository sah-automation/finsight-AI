# FinSight AI - Makefile
# Usage: make <target>
# Key targets: check, ci, test, format, config-check

COVERAGE_MIN ?= 50

.PHONY: help install install-dev install-hooks format lint typecheck imports vulture secrets pre-commit check ci test test-unit test-integration test-golden test-contract test-architecture test-switches test-security arch-test coverage coverage-html config-check migrate migration docker-up docker-down clean update-deps

# Default target
help:
	@echo "FinSight AI - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  install        - Install production dependencies"
	@echo "  install-dev    - Install dev dependencies"
	@echo "  install-hooks  - Install pre-commit hooks"
	@echo ""
	@echo "Quality Gates (run all):"
	@echo "  check          - Run every gate once (lint + typecheck + imports + vulture + secrets + tests + security)"
	@echo "  ci             - CI pipeline (lint + typecheck + imports + vulture + secrets + coverage incl. security)"
	@echo "  pre-commit     - Run pre-commit on all files"
	@echo ""
	@echo "Individual Checks:"
	@echo "  format         - Auto-format and auto-fix src and tests"
	@echo "  lint           - Run ruff (lint + format check)"
	@echo "  typecheck      - Run mypy --strict"
	@echo "  imports        - Run import-linter"
	@echo "  vulture        - Run dead code detection"
	@echo "  secrets        - Run detect-secrets"
	@echo "  config-check   - Validate every config profile through the loader"
	@echo "  arch-test      - Run architecture invariant tests"
	@echo ""
	@echo "Tests:"
	@echo "  test           - Run all tests (unit + contract + architecture + switches)"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-golden    - Run golden set tests"
	@echo "  test-contract  - Run contract tests"
	@echo "  test-architecture - Run architecture invariant tests"
	@echo "  test-switches  - Run switch path tests"
	@echo "  test-security  - Run security tests (isolation, permissions, cache keys, evidence, PII)"
	@echo ""
	@echo "Database:"
	@echo "  docker-up      - Start the local test stack (Postgres, LocalStack, Redis, OTel)"
	@echo "  docker-down    - Stop the local test stack and delete its volumes"
	@echo "  migrate        - Apply all migrations (alembic upgrade head)"
	@echo "  migration      - Create a migration (make migration m=\"message\")"
	@echo ""
	@echo "Coverage:"
	@echo "  coverage       - Generate coverage report and enforce the floor (COVERAGE_MIN, default 50)"
	@echo "  coverage-html  - Generate HTML coverage report"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean          - Remove build artifacts"
	@echo "  update-deps    - Update dependencies to latest allowed versions"

# ============================================================
# Installation
# ============================================================
install:
	uv sync --frozen

install-dev:
	uv sync --frozen --all-extras

install-hooks:
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

# ============================================================
# Quality Gates
# ============================================================
check: lint typecheck imports vulture secrets test test-security
	@echo "✓ All quality checks passed"

ci: lint typecheck imports vulture secrets coverage
	@echo "✓ CI pipeline passed"

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

lint:
	uv run ruff check src tests --exit-non-zero-on-fix
	uv run ruff format --check src tests

typecheck:
	uv run mypy src --strict --show-error-codes

imports:
	uv run lint-imports --verbose

vulture:
	uv run vulture src/finsight --min-confidence=80

secrets:
	uv run pre-commit run detect-secrets --all-files  # pragma: allowlist secret

pre-commit:
	uv run pre-commit run --all-files

config-check:
	uv run python scripts/check_config.py

# ============================================================
# Architecture Tests
# ============================================================
arch-test:
	uv run pytest tests/architecture -v --tb=short

# ============================================================
# Test Suite
# ============================================================
test: test-unit test-contract test-architecture test-switches
	@echo "✓ All test suites passed"

test-unit:
	uv run pytest tests/unit -v --tb=short -m "unit"

test-integration:
	ENVIRONMENT=test uv run pytest tests/integration -v --tb=short -m "integration"

test-golden:
	uv run pytest tests/golden -v --tb=short -m "golden"

test-contract:
	uv run pytest tests/contract -v --tb=short -m "contract"

test-architecture:
	uv run pytest tests/architecture -v --tb=short -m "architecture"

test-switches:
	uv run pytest tests/unit/switches -v --tb=short -m "switch"

test-security:
	uv run pytest tests/security -v --tb=short -m "security"

# ============================================================
# Database
# ============================================================
migrate:
	uv run alembic upgrade head

migration:
	@test -n "$(m)" || (echo "Usage: make migration m=\"describe the change\"" && exit 1)
	uv run alembic revision -m "$(m)"

docker-up:
	docker compose -f docker-compose.test.yml up -d --wait

docker-down:
	docker compose -f docker-compose.test.yml down -v

# ============================================================
# Coverage
# ============================================================
coverage:
	uv run pytest tests/unit tests/contract tests/architecture tests/security \
		--cov=src/finsight --cov-report=term-missing --cov-report=xml \
		--cov-fail-under=$(COVERAGE_MIN)

coverage-html:
	uv run pytest tests/unit tests/contract tests/architecture tests/security \
		--cov=src/finsight --cov-report=html

# ============================================================
# Maintenance
# ============================================================
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

update-deps:
	uv lock --upgrade
	uv sync --all-extras
