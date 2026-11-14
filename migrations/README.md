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

## Round-trip verification (integration / CI)

The migration chain must pass `upgrade head → downgrade base → upgrade head`
against the test database.  An integration test lives at
`tests/integration/test_migration_roundtrip.py` and verifies that the final
upgrade recreates:

- all company-scoped (partitioned) core tables:
  `documents`, `document_chunks`, `metrics`, `answers`, `audit_logs`,
  `document_versions`, `jobs`, `document_tables` (`PARTITION BY LIST (company_id)`);
- the `document_chunks` HNSW vector index (`ix_document_chunks_embedding_hnsw`);
- the hybrid-search GIN index (`ix_document_chunks_search_vector`);
- row-level security on the tenant tables.

The test is integration-only: it requires a live PostgreSQL instance and skips
cleanly when the service is unavailable.  Staging/CI must still run the
destructive checks that cannot execute against a shared or production database,
including:

- downgrade of the *full* chain on a database populated with tenant/company
  partitions (verifies `CASCADE` drops and metadata cleanup), then re-apply;
- migration performance and locking on databases with ~1,000 company partitions;
- re-creation of per-company partitions after the round trip through the
  `PartitionManager` adapter;
- vector-index build time under production data volumes.

Those checks are documented here and executed in staging/CI rather than in the
default local suite.

Migrations are hand-written SQL until SQLAlchemy models land in
`src/finsight/adapters/repositories`. `target_metadata` is `None`, so
`alembic check` is not enabled yet. Do not hard-code a database URL here or in
`alembic.ini`.
