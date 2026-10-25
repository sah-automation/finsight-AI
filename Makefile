# FinSight AI - Makefile
# Usage: make <target>
# Key targets: check, test, lint, typecheck, arch-test, install-hooks

.PHONY: help install install-dev install-hooks check lint typecheck test test-unit test-integration test-golden test-contract test-architecture test-switches arch-test clean coverage ci

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
	@echo "  check          - Run all quality checks (lint + typecheck + imports + vulture + secrets + tests)"
	@echo "  ci             - Full CI pipeline (same as check but with coverage)"
	@echo ""
	@echo "Individual Checks:"
	@echo "  lint           - Run ruff (lint + format check)"
	@echo "  typecheck      - Run mypy --strict"
	@echo "  imports        - Run import-linter"
	@echo "  vulture        - Run dead code detection"
	@echo "  secrets        - Run detect-secrets"
	@echo "  arch-test      - Run architecture invariant tests"
	@echo ""
	@echo "Tests:"
	@echo "  test           - Run all tests (unit + integration + contract + architecture + switches)"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-golden    - Run golden set tests"
	@echo "  test-contract  - Run contract tests"
	@echo "  test-architecture - Run architecture invariant tests"
	@echo "  test-switches  - Run switch path tests"
	@echo ""
	@echo "Coverage:"
	@echo "  coverage       - Generate coverage report"
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
check: lint typecheck imports vulture secrets arch-test test
	@echo "✓ All quality checks passed"

ci: check coverage
	@echo "✓ CI pipeline passed"

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
	uv run detect-secrets-hook --baseline .secrets.baseline $$(git ls-files -co --exclude-standard)

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

# ============================================================
# Coverage
# ============================================================
coverage:
	uv run pytest tests/unit tests/contract tests/architecture \
		--cov=src/finsight --cov-report=term-missing --cov-report=xml

coverage-html:
	uv run pytest tests/unit tests/contract tests/architecture \
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
