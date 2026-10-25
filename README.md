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

- Python 3.12+
- uv (recommended) or pip
- Docker + Docker Compose (for local services)
- AWS CLI (for deployment)

### Installation

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --frozen --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

### Local Development

```bash
# Start local services (PostgreSQL, LocalStack, Redis, OTel)
docker compose -f docker-compose.test.yml up -d

# Run tests
make test

# Run quality checks
make check

# Start API server (when implemented)
uv run uvicorn src.finsight.entrypoints.api.main:app --reload
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
docs/                   # Architecture, plans, ADRs
```

## Configuration

All configuration lives in `config/`:

- `schema.yaml` - Single source of truth (structure, defaults, validation)
- `dev.yaml` / `staging.yaml` / `prod.yaml` - Environment overrides
- `permissions.yaml` - RBAC rules
- `prices.yaml` - Model pricing for metering

**Rules:**
- Only `core/config` reads config files/env vars
- No hard-coded values - everything from config
- Both paths of every switch must exist and be tested
- Invalid config fails loudly at startup

## Quality Gates

Run locally:
```bash
make check        # lint + typecheck + imports + vulture + secrets + architecture + tests
make test         # unit + contract + architecture + switch suites
make arch-test    # architecture invariant tests only
make test-switches # switch ON/OFF path tests only
```

Standards enforcement status and remaining work:
`docs/plans/quality-standards-enforcement.md`. Decision record:
`docs/adr/0001-standards-enforcement.md`.

CI Pipeline (`.github/workflows/ci.yml`):
1. Lint (ruff) + Format check
2. Typecheck (mypy --strict)
3. Import architecture (lint-imports)
4. Dead code detection (vulture)
5. Secret detection (detect-secrets)
6. Architecture invariant tests
7. Unit tests
8. Contract tests
9. Switch path tests
10. Integration tests (with LocalStack/PostgreSQL)
11. Golden set tests (pilot + standard config)
12. Security tests
13. Build verification

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

See `docs/plans/Project Requirement/finsight_config_switches.md` for:
- 5 pilot switches + AI model swap
- Strict rules (no hard-coding, one config reader, both paths tested, fail loudly)
- Validation rules
- Rollback procedures
- Cost impact

## Documentation

- `docs/plans/Project Requirement/FinSightAI.md` - Project requirements
- `docs/plans/architecture/phase1/finsight_mvp_hld.svg` - High-level design diagram
- `docs/adr/` - Architecture Decision Records (to be created)
- `GLOSSARY.md` - Domain vocabulary (to be created)

## License

Proprietary - All rights reserved.