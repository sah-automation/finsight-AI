"""convert core tables to partitioned structure with RLS

Revision ID: 0003_partitioned_tables
Revises: 0002_partition_metadata
Create Date: 2026-10-28 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alembic import op
from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '0003_partitioned_tables'
down_revision: str | None = '0002_partition_metadata'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARENT_TABLES_WITH_COMPANY = ['documents', 'document_chunks', 'metrics', 'answers']
TABLES_TO_PARTITION = ['documents', 'document_chunks', 'metrics', 'answers', 'audit_logs']


def _table_exists(conn: Any, table: str) -> bool:  # type: ignore[name-defined]
    result = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            """
        ),
        {'table': table},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Convert tenant tables to partitioned structure with RLS."""
    conn = op.get_bind()

    for table in TABLES_TO_PARTITION:
        try:
            if not _table_exists(conn, table):
                continue
            result = conn.execute(
                text(
                    """
                    SELECT c.relkind
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = :table AND n.nspname = 'public'
                    """
                ),
                {'table': table},
            )
            row = result.fetchone()
            if row and row[0] == 'p':  # already partitioned
                continue
        except Exception:
            pass

        try:
            op.execute(f'ALTER TABLE {table} RENAME TO {table}_old')
        except Exception:
            continue

        try:
            op.execute(
                f'CREATE TABLE {table} (LIKE {table}_old INCLUDING DEFAULTS) PARTITION BY LIST (company_id)'
            )
        except Exception:
            # Restore if partitioned creation failed
            op.execute(f'ALTER TABLE {table}_old RENAME TO {table}')
            continue

        try:
            op.execute(f'INSERT INTO {table} SELECT * FROM {table}_old')
        except Exception:
            pass

        try:
            op.execute(f'ALTER TABLE {table} ADD PRIMARY KEY (id, company_id)')
        except Exception:
            pass

        try:
            op.execute(f'DROP TABLE {table}_old CASCADE')
        except Exception:
            pass

    # Enable RLS on parent/tenant tables
    for table in PARENT_TABLES_WITH_COMPANY:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS {table}_company_isolation ON {table}')
        op.execute(
            f"""
            CREATE POLICY {table}_company_isolation ON {table}
                USING (company_id = current_setting('app.company_id', true)::uuid)
            """
        )

    # Also enable RLS on audit_logs if present
    try:
        op.execute('ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY')
        op.execute('DROP POLICY IF EXISTS audit_logs_company_isolation ON audit_logs')
        op.execute(
            """
            CREATE POLICY audit_logs_company_isolation ON audit_logs
                USING (company_id = current_setting('app.company_id', true)::uuid)
            """
        )
    except Exception:
        pass

    # Ensure company_id indexes exist first on tenant tables
    op.execute('CREATE INDEX IF NOT EXISTS ix_documents_company_id ON documents (company_id)')
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_document_chunks_company_id ON document_chunks (company_id)'
    )
    op.execute('CREATE INDEX IF NOT EXISTS ix_metrics_company_id ON metrics (company_id)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_answers_company_id ON answers (company_id)')
    try:
        op.execute('CREATE INDEX IF NOT EXISTS ix_audit_logs_company_id ON audit_logs (company_id)')
    except Exception:
        pass

    # Ensure HNSW vector index structure exists for document_chunks
    try:
        op.execute(
            'CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw '
            'ON document_chunks USING hnsw (embedding vector_cosine_ops) '
            'WITH (m = 16, ef_construction = 200)'
        )
    except Exception:
        pass


def downgrade() -> None:
    """Revert RLS policies."""
    try:
        op.execute('DROP POLICY IF EXISTS audit_logs_company_isolation ON audit_logs')
        op.execute('ALTER TABLE audit_logs NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY')
    except Exception:
        pass

    for table in reversed(PARENT_TABLES_WITH_COMPANY):
        try:
            op.execute(f'DROP POLICY IF EXISTS {table}_company_isolation ON {table}')
            op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
        except Exception:
            pass
