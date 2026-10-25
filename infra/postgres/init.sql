-- Initialisation for the integration-test PostgreSQL instance.
-- pgvector must exist before any vector columns or indexes are created.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
