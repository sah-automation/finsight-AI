"""Integration test for the Alembic migration chain.

Exercises the full migration history against a real PostgreSQL instance:
upgrade to head, downgrade to base, then upgrade to head again.  Confirms
that the partitioned (company-scoped) core tables and the vector (HNSW)
indexes are present after the final upgrade.

The test is integration-only: it requires a live Postgres instance with the
test profile credentials (ENVIRONMENT=test).  When the service is unavailable
the test is skipped.
"""

from __future__ import annotations

import socket
from pathlib import Path
from urllib.parse import quote_plus

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from finsight.core.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / 'migrations'
ALEMBIC_INI = REPO_ROOT / 'alembic.ini'

# All company-scoped core tables that must be partitioned (``PARTITION BY LIST
# (company_id)``) after an upgrade.
_PARTITIONED_TABLES = (
    'documents',
    'document_chunks',
    'metrics',
    'answers',
    'audit_logs',
    'document_versions',
    'jobs',
    'document_tables',
)


def _postgres_reachable() -> bool:
    try:
        settings = load_config().vector_store
        with socket.create_connection((str(settings.host), int(settings.port)), timeout=2):
            return True
    except Exception:  # pragma: no cover - exercised only without Postgres  # noqa: BLE001
        return False


def _database_url() -> str:
    settings = load_config().vector_store
    username = quote_plus(settings.username)
    password = quote_plus(settings.password)
    return (
        f'postgresql+psycopg://{username}:{password}'
        f'@{settings.host}:{settings.port}/{settings.database}'
        f'?sslmode={settings.ssl_mode}'
    )


pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(300),
    pytest.mark.skipif(
        not _postgres_reachable(),
        reason='PostgreSQL is not available (integration-only test)',
    ),
]


def test_migration_round_trip_recreates_partitioned_tables_and_vector_index() -> None:
    """Upgrade -> downgrade -> upgrade leaves the schema complete."""
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option('script_location', str(MIGRATIONS_DIR))

    # Leave the database at base, then walk up/down/up once more.
    command.downgrade(alembic_cfg, 'base')
    command.upgrade(alembic_cfg, 'head')
    command.downgrade(alembic_cfg, 'base')
    command.upgrade(alembic_cfg, 'head')

    engine = create_engine(_database_url(), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            _assert_partitioned_tables(connection)
            _assert_vector_indexes(connection)
            _assert_rls_enabled(connection)
    finally:
        engine.dispose()


def _assert_partitioned_tables(connection: object) -> None:
    for table_name in _PARTITIONED_TABLES:
        relkind = connection.execute(
            text(
                """
                SELECT c.relkind
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = :table_name
                """
            ),
            {'table_name': table_name},
        ).scalar()
        assert relkind == 'p', (
            f'{table_name} is not a partitioned table after upgrade (relkind={relkind!r})'
        )


def _assert_vector_indexes(connection: object) -> None:
    for index_name in (
        'ix_document_chunks_embedding_hnsw',
        'ix_document_chunks_search_vector',
    ):
        present = connection.execute(
            text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'document_chunks'
                  AND indexname = :index_name
                """
            ),
            {'index_name': index_name},
        ).scalar()
        assert present == 1, f'document_chunks vector index {index_name} is missing'


def _assert_rls_enabled(connection: object) -> None:
    for table_name in _PARTITIONED_TABLES:
        enabled = connection.execute(
            text(
                """
                SELECT relrowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = :table_name
                """
            ),
            {'table_name': table_name},
        ).scalar()
        assert enabled is True, f'row level security is not enabled on {table_name}'
