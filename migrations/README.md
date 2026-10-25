# Database migrations

Alembic migrations for the PostgreSQL + pgvector schema.

- `alembic.ini` holds the Alembic setup only; the database URL is built in
  `env.py` from `finsight.core.config`.
- `env.py` loads the active `ENVIRONMENT` profile (default `development`).
- `versions/` contains the ordered migrations.

```bash
# Start the local Postgres
make docker-up

# Apply every migration
ENVIRONMENT=test make migrate

# Create a new migration (hand-written SQL for now)
make migration m="add invoices table"

# Roll back one revision
ENVIRONMENT=test uv run alembic downgrade -1
```

Migrations are hand-written SQL until SQLAlchemy models land in
`src/finsight/adapters/repositories`. `target_metadata` is `None`, so
`alembic check` is not enabled yet. Do not hard-code a database URL here or in
`alembic.ini`.
