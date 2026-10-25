# Contributing

FinSight AI is a multi-tenant financial intelligence platform. Read
`CODING_STANDARDS.md` before changing code: it defines the layers, dependency
direction, DI rules, and the section 17 checklist every pull request uses.

## Setup

```bash
# Python 3.12 comes from .python-version (uv reads it automatically)
uv sync --frozen --all-extras

# Local environment template (test profile)
cp .env.example .env
set -a; source .env; set +a

# pre-commit + commit-msg hooks
make install-hooks
```

`uv sync` is the only supported install path. Local and CI both read
`.python-version`, so the interpreter cannot drift.

## Local services

```bash
make docker-up    # Postgres + pgvector, LocalStack, Redis, OTel
make docker-down  # stop and delete volumes
```

The compose stack matches `config/test.yaml` and `.env.example`.

## Database migrations

Alembic migrations live in `migrations/`. The database URL is built in
`migrations/env.py` from `finsight.core.config`; never hard-code it in
`alembic.ini` or a migration.

```bash
# Apply every migration to the local test database
ENVIRONMENT=test make migrate
# or: ENVIRONMENT=test uv run alembic upgrade head

# Create a migration (hand-written SQL until ORM models exist)
make migration m="add invoices table"
```

Rules:

- `alembic upgrade head` must work on an empty database.
- `alembic downgrade base` must work and leave no core tables behind.
- `upgrade head` must be idempotent on an already-migrated database.
- Migrations carry `company_id` on every tenant-owned table.
- The CI `Migrations` job runs upgrade → downgrade → upgrade.
- `alembic check` is not enabled yet because `target_metadata` is `None` until
  SQLAlchemy models land in `adapters/repositories`.

## Tests and gates

```bash
make format       # ruff format + ruff check --fix
make check        # every gate once: lint, types, imports, vulture, secrets, tests
make ci           # same gates plus the coverage floor
make coverage     # coverage floor (COVERAGE_MIN, default 50)
make config-check # load every config profile through the typed loader
```

CI runs the same commands plus pre-commit, migrations, dependency audit,
dependency review, and integration tests. The `Summary` check is the required
branch-protection status.

## Commit messages and pull requests

- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`,
  `chore:`, `test:`, `ci:`, ...). The `commit-msg` hook enforces this.
- One purpose per pull request. Use the PR template and tick the section 17
  checklist.
- State which layers changed, which config switches changed, how you tested,
  and how to roll back.
- Do not weaken a gate to make it pass. If a gate is wrong, change the gate and
  record why in the PR.

## Security

Never commit credentials. Report vulnerabilities privately as described in
`SECURITY.md`, not in a public issue.
