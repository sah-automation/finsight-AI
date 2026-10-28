"""add jobs and document versions tables

Revision ID: 0004_jobs_document_versions
Revises: 0003_partitioned_tables
Create Date: 2026-10-28 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '0004_jobs_document_versions'
down_revision: str | None = '0003_partitioned_tables'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the jobs table and a state-bearing document_versions table."""
    # State-bearing document version representation (partitioned by company).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_versions (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            document_id uuid NOT NULL,
            FOREIGN KEY (document_id, company_id)
                REFERENCES documents (id, company_id) ON DELETE CASCADE,
            version integer NOT NULL DEFAULT 1,
            state text NOT NULL DEFAULT 'received'
                CHECK (
                    state IN (
                        'received',
                        'stored',
                        'processing',
                        'committed',
                        'failed',
                        'needs_review',
                        'superseded',
                        'rejected'
                    )
                ),
            file_hash text,
            filename text,
            category text,
            review_scope text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_document_versions_company_document_version
                UNIQUE (company_id, document_id, version),
            PRIMARY KEY (id, company_id)
        ) PARTITION BY LIST (company_id)
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_document_versions_company_id '
        'ON document_versions (company_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_document_versions_company_document '
        'ON document_versions (company_id, document_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_document_versions_company_state '
        'ON document_versions (company_id, state)'
    )

    # Enable RLS.
    op.execute('ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE document_versions FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS document_versions_company_isolation ON document_versions')
    op.execute(
        """
        CREATE POLICY document_versions_company_isolation ON document_versions
            USING (company_id = current_setting('app.company_id', true)::uuid)
            WITH CHECK (company_id = current_setting('app.company_id', true)::uuid)
        """
    )

    # Jobs table (Aurora is the source of truth for job status/progress).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            job_id uuid NOT NULL DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            document_id uuid,
            document_version_id uuid,
            FOREIGN KEY (document_id, company_id)
                REFERENCES documents (id, company_id) ON DELETE CASCADE,
            FOREIGN KEY (document_version_id, company_id)
                REFERENCES document_versions (id, company_id) ON DELETE CASCADE,
            status text NOT NULL DEFAULT 'queued'
                CHECK (
                    status IN (
                        'queued',
                        'processing',
                        'committed',
                        'failed',
                        'retrying'
                    )
                ),
            progress integer NOT NULL DEFAULT 0
                CHECK (progress >= 0 AND progress <= 100),
            error text,
            receive_count integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            completed_at timestamptz,
            CONSTRAINT uq_jobs_company_job_id UNIQUE (company_id, job_id),
            PRIMARY KEY (id, company_id)
        ) PARTITION BY LIST (company_id)
        """
    )
    op.execute('UPDATE jobs SET job_id = id WHERE job_id IS NULL')
    op.execute('CREATE INDEX IF NOT EXISTS ix_jobs_company_id ON jobs (company_id)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_jobs_company_status ON jobs (company_id, status)')
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_jobs_company_created ON jobs (company_id, created_at)'
    )

    # Enable RLS.
    op.execute('ALTER TABLE jobs ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE jobs FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS jobs_company_isolation ON jobs')
    op.execute(
        """
        CREATE POLICY jobs_company_isolation ON jobs
            USING (company_id = current_setting('app.company_id', true)::uuid)
            WITH CHECK (company_id = current_setting('app.company_id', true)::uuid)
        """
    )



def downgrade() -> None:
    """Drop jobs and document_versions tables and revert RLS policies."""
    op.execute('DROP POLICY IF EXISTS jobs_company_isolation ON jobs')
    op.execute('ALTER TABLE jobs NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE jobs DISABLE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS document_versions_company_isolation ON document_versions')
    op.execute('ALTER TABLE document_versions NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE document_versions DISABLE ROW LEVEL SECURITY')
    op.execute('DROP TABLE IF EXISTS jobs CASCADE')
    op.execute('DROP TABLE IF EXISTS document_versions CASCADE')
