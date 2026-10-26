# FinSight AI

Financial Intelligence Platform - Multi-tenant platform for document ingestion, metric extraction, RAG-based Q&A, forecasting, and decision support.

## Architecture

- **Backend**: Python 3.12+, FastAPI, deployed as AWS Lambda zip packages
- **Orchestration**: LangGraph + LangChain (multi-agent: supervisor + specialists)
- **Data**: Aurora PostgreSQL (pgvector) for structured data + vectors, S3 for raw files, DynamoDB for cache/state
- **AI**: Model-agnostic via LiteLLM gateway, hybrid retrieval (vector + keyword) with reranking
- **Infra**: Containerized (Docker), CI/CD, deployable to AWS
- **Security**: Per-company isolation, RBAC (admin/finance manager/analyst/viewer), encryption at rest/in transit, audit logs

## Quick Start

### Prerequisites

- Python 3.12 (the tracked `.python-version` file pins it; `uv` reads it)
- uv (recommended) or pip
- Docker + Docker Compose (for local services)
- AWS CLI (for deployment)

### Installation

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (selects Python 3.12 from .python-version)
uv sync --frozen --all-extras

# Copy the local environment template and export it in your shell
cp .env.example .env
set -a; source .env; set +a

# Install pre-commit hooks (pre-commit + commit-msg)
make install-hooks
```

`.env.example` targets the local test profile (`ENVIRONMENT=test`), which matches
`docker-compose.test.yml` and `config/test.yaml`. Every variable in it is a safe
placeholder. See the comments in the file for what each value controls.

### Local Development

```bash
# Start local services (PostgreSQL, LocalStack, Redis, OTel)
make docker-up

# Apply database migrations
ENVIRONMENT=test make migrate

# Run tests
make test

# Run integration tests against the local stack (uses ENVIRONMENT=test)
make test-integration

# Run quality checks
make check

# Validate every config profile
make config-check

# Validate every relative Markdown link
make docs-check

# Stop local services and delete volumes
make docker-down

# Start API server (when implemented)
uv run uvicorn finsight.entrypoints.api.main:app --reload  # when entrypoint exists
```

## Project Structure

```
src/finsight/
  core/                 # Shared basics, no business rules
    config/             # ONLY place that reads config/env
    errors/             # Custom error types
    logging/            # Logger, trace tags
    types/              # Shared IDs, enums

  domain/               # Pure business logic (no vendor imports)
    entities/           # Document, Chunk, Metric, Answer, Recommendation
    value_objects/      # Money, Period, Citation, Confidence
    services/           # Business rules (evidence check, conflict rules)
    ports/              # Interfaces (abstract classes)

  application/          # Use cases (orchestrate domain + ports)
    ask_question/       # Question flow steps
    ingest_document/    # Ingestion flow steps
    metrics/
    forecasting/
    risk_alerts/
    decisions/
    reports/

  adapters/             # Vendor implementations (implement ports)
    llm/                # LiteLLM gateway, router, fallbacks
    embedding/          # Embedding providers
    vector_store/       # Aurora pgvector
    rerank/             # Cohere reranker
    readers/            # pdfplumber, tesseract, textract, excel, csv, docx
    repositories/       # Aurora Postgres access
    storage/            # S3
    queue/              # SQS
    cache/              # DynamoDB
    auth/               # Cognito
    metering/           # Usage tracking

  entrypoints/          # Thin doors (no logic)
    api/                # Upload, status, question, source_viewer
    workers/            # SQS/Step Functions handlers
    scheduled/          # Reports, weekly jobs

  composition/          # Wires everything together (composition root)

config/
  schema.yaml           # Config schema + validation rules
  dev.yaml              # Development overrides
  staging.yaml          # Staging overrides
  prod.yaml             # Production overrides
  permissions.yaml      # RBAC permissions
  prices.yaml           # Model/API pricing

tests/
  unit/                 # Mirrors src/, fast, fakes for ports
  integration/          # Real adapters, real services
  golden/               # 100+ question set (pilot + standard config)
  contract/             # One test per port, run against every adapter
  architecture/         # Invariant tests (AST-based)

infra/                  # Infrastructure code
migrations/             # Alembic migrations (schema history)
scripts/                # Developer and CI helper scripts
docs/                   # Architecture, plans, ADRs
```

## Configuration

All configuration lives in `config/`:

- `schema.yaml` - Single source of truth (structure, defaults, validation)
- `dev.yaml` / `test.yaml` / `staging.yaml` / `prod.yaml` - Environment overrides
- `permissions.yaml` - RBAC rules
- `prices.yaml` - Model pricing for metering

**Rules:**
- Only `core/config` reads config files/env vars
- No hard-coded values - everything from config
- Both paths of every switch must exist and be tested
- Invalid config fails loudly at startup

## Database Migrations

Alembic migrations live in `migrations/`. The database URL is built in
`migrations/env.py` from `finsight.core.config`, so migrations use the active
profile instead of a hard-coded URL.

```bash
make docker-up                     # start Postgres + pgvector
ENVIRONMENT=test make migrate      # apply every migration
make migration m="add invoices"    # create a migration
ENVIRONMENT=test uv run alembic downgrade base   # roll back
```

The CI `Migrations` job runs `upgrade head` → `downgrade base` → `upgrade head`
against the compose Postgres. See `CONTRIBUTING.md` for the rules.

## Quality Gates

Run locally:
```bash
make check        # lint + typecheck + imports + vulture + secrets + tests + security
make ci           # the same gates plus the coverage floor
make format       # auto-format and auto-fix src and tests
make pre-commit   # run every pre-commit hook on all files
make coverage     # coverage floor (COVERAGE_MIN, default 50)
make config-check # validate every environment profile through the loader
make docs-check   # verify every relative Markdown link resolves
make test         # unit + contract + architecture + switch suites
make arch-test    # architecture invariant tests only
make test-switches # switch ON/OFF path tests only
```

Coverage is enforced at 50% line+branch for `src/finsight`
(`fail_under` in `pyproject.toml`, `--cov-fail-under` in `make coverage`).
Migrations, `conftest.py`, and generated code are excluded. Raise the floor as
the suite grows; see `docs/plans/quality-standards-enforcement.md`.

Standards enforcement status and remaining work:
`docs/plans/quality-standards-enforcement.md`. Decision record:
`docs/adr/0001-standards-enforcement.md`.

CI Pipeline (`.github/workflows/ci.yml`):
1. Lint (ruff) + Format check
2. Typecheck (mypy --strict)
3. Import architecture (lint-imports)
4. Dead code detection (vulture)
5. Secret detection (detect-secrets)
6. Pre-commit (all hooks, including YAML and shell checks) and Markdown link check
7. Architecture invariant tests
8. Unit tests
9. Coverage floor (50% line+branch) with `coverage.xml` artifact
10. Contract tests
11. Switch path tests
12. Integration tests (with LocalStack/PostgreSQL)
13. Database migrations (upgrade, downgrade, re-apply)
14. Golden set tests (pilot + standard config)
15. Security tests
16. Dependency audit (`pip-audit`) and dependency review on PRs
17. Build verification (wheel, Lambda zip, container image)
18. Infrastructure synth (CDK stacks + smoke tests, non-deploying)

## Packaging and Infrastructure

```bash
make lambda-build   # build dist/lambda/api.zip + sha256 (app + config only)
make docker-build   # build the runtime container image
make infra-synth    # synthesize every CDK stack, no AWS credentials
make infra-test     # CDK smoke tests
```

Deployment is **not wired yet**: `infra/cdk/` is a validated scaffold, there is
no deploy workflow, and no AWS resources exist. See
[`docs/deployment.md`](docs/deployment.md) and issue #10.

## Coding Standards

See `CODING_STANDARDS.md` for:
- Dependency direction rules
- OOP/SOLID principles mapped to FinSight
- Design patterns to use
- Config rules (from config switch guide)
- Error handling
- Security & company separation
- Numbers & money (Decimal only)
- Testing requirements (85%+ on domain/application)
- Observability (tracing, metering, alerts)
- Git/release rules
- PR checklist (section 17)

## Config Switches

See `docs/plans/project_requirement/finsight_config_switches.md` for:
- 5 pilot switches + AI model swap
- Strict rules (no hard-coding, one config reader, both paths tested, fail loudly)
- Validation rules
- Rollback procedures
- Cost impact

## Documentation

- `docs/plans/project_requirement/finsightAI.md` - Project requirements
- `docs/plans/architecture/phase1/finsight_mvp_hld.svg` - High-level design diagram
- `docs/adr/` - Architecture Decision Records
- `docs/deployment.md` - Deployment guide (scaffolding status)
- `docs/onboarding.md` - Developer onboarding
- `docs/runbook.md` - Operational procedures (scaffolding status)
- [`GLOSSARY.md`](GLOSSARY.md) - Domain vocabulary

## Contributing

See `CONTRIBUTING.md` for setup, migrations, tests, and the pull request
process. Every PR uses the template in `.github/pull_request_template.md` and
the section 17 checklist from `CODING_STANDARDS.md`.

## Commit Messages

Commits must follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `ci:`, ...). The `commit-msg`
pre-commit hook enforces this. `make install-hooks` installs both the
`pre-commit` and `commit-msg` hooks.

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
