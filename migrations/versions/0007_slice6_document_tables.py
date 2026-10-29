"""slice 6.2: document_tables partitioned persistence

Revision ID: 0007_slice6_document_tables
Revises: 0006_slice5_4_retrieval
Create Date: 2026-10-29 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '0007_slice6_document_tables'
down_revision: str | None = '0006_slice5_4_retrieval'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_tables (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            document_id uuid REFERENCES documents (id) ON DELETE CASCADE,
            version_id uuid,
            page integer,
            page_number integer,
            positional_index integer NOT NULL DEFAULT 0,
            table_index integer NOT NULL DEFAULT 0,
            table_id text,
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            html text,
            needs_review boolean NOT NULL DEFAULT false,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_document_tables_company_version_table
                UNIQUE (company_id, version_id, table_id),
            PRIMARY KEY (id, company_id)
        ) PARTITION BY LIST (company_id)
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_document_tables_company_id ON document_tables (company_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_document_tables_company_version '
        'ON document_tables (company_id, version_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_document_tables_company_page '
        'ON document_tables (company_id, page_number)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_document_tables_company_table_id '
        'ON document_tables (company_id, table_id)'
    )

    op.execute('ALTER TABLE document_tables ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE document_tables FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS document_tables_company_isolation ON document_tables')
    op.execute(
        """
        CREATE POLICY document_tables_company_isolation ON document_tables
            USING (company_id = current_setting('app.company_id', true)::uuid)
            WITH CHECK (company_id = current_setting('app.company_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS document_tables_company_isolation ON document_tables')
    op.execute('ALTER TABLE document_tables NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE document_tables DISABLE ROW LEVEL SECURITY')
    op.execute('DROP TABLE IF EXISTS document_tables CASCADE')
