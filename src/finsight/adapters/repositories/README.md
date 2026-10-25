# Repositories

Aurora (Postgres) data access implementing repository ports.

**Implements:** `DocumentRepository`, `ChunkRepository`, `MetricRepository`, etc.

**Belongs here:**
- SQLAlchemy models (private to this folder)
- Query builders with mandatory `company_id` filter
- Upsert logic for idempotent jobs
- Connection pooling

**Rules:**
- Every method requires `company_id`
- Business code never writes SQL
- Repository proxy adds role/company checks

**Does not belong here:**
- Vector operations (that's vector_store/)
- Business logic
- Migration scripts (those go in infra/)