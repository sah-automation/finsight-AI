"""initial core schema

Creates the multi-tenant core tables and the pgvector extension.

Embedding dimension (1024) and HNSW parameters (m = 16,
ef_construction = 200) mirror `config/schema.yaml`; migrations are historical
snapshots, so they keep literal values instead of reading live config.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-26

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the core schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.execute(
        """
        CREATE TABLE companies (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name text NOT NULL,
            slug text NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            email text NOT NULL,
            role text NOT NULL
                CHECK (role IN ('admin', 'finance_manager', 'analyst', 'viewer')),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_users_company_email UNIQUE (company_id, email)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            uploaded_by uuid REFERENCES users (id) ON DELETE SET NULL,
            filename text NOT NULL,
            content_type text,
            storage_key text NOT NULL,
            checksum_sha256 text,
            document_type text,
            period_start date,
            period_end date,
            status text NOT NULL DEFAULT 'received'
                CHECK (status IN ('received', 'stored', 'processing', 'committed', 'failed')),
            page_count integer CHECK (page_count IS NULL OR page_count >= 0),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute('CREATE INDEX ix_documents_company_status ON documents (company_id, status)')
    op.execute(
        'CREATE INDEX ix_documents_company_period '
        'ON documents (company_id, period_start, period_end)'
    )
    op.execute(
        """
        CREATE TABLE document_chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            document_id uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
            parent_id uuid REFERENCES document_chunks (id) ON DELETE CASCADE,
            chunk_index integer NOT NULL,
            content text NOT NULL,
            token_count integer NOT NULL CHECK (token_count >= 0),
            page_from integer,
            page_to integer,
            embedding vector(1024),
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_document_chunks_document_index UNIQUE (document_id, chunk_index)
        )
        """
    )
    op.execute(
        'CREATE INDEX ix_document_chunks_company_document '
        'ON document_chunks (company_id, document_id)'
    )
    op.execute(
        'CREATE INDEX ix_document_chunks_embedding_hnsw '
        'ON document_chunks USING hnsw (embedding vector_cosine_ops) '
        'WITH (m = 16, ef_construction = 200)'
    )
    op.execute(
        """
        CREATE TABLE metrics (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            document_id uuid REFERENCES documents (id) ON DELETE SET NULL,
            name text NOT NULL,
            value numeric(20, 4) NOT NULL,
            unit text,
            currency char(3),
            period_start date NOT NULL,
            period_end date NOT NULL,
            source_page integer,
            source_table text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        'CREATE INDEX ix_metrics_company_name_period ON metrics (company_id, name, period_end)'
    )
    op.execute(
        """
        CREATE TABLE answers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            user_id uuid REFERENCES users (id) ON DELETE SET NULL,
            question text NOT NULL,
            answer text NOT NULL,
            citations jsonb NOT NULL DEFAULT '[]'::jsonb,
            model_id text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute('CREATE INDEX ix_answers_company_created ON answers (company_id, created_at)')
    op.execute(
        """
        CREATE TABLE audit_logs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid REFERENCES companies (id) ON DELETE SET NULL,
            actor_id uuid REFERENCES users (id) ON DELETE SET NULL,
            action text NOT NULL,
            resource_type text NOT NULL,
            resource_id text,
            detail jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute('CREATE INDEX ix_audit_logs_company_created ON audit_logs (company_id, created_at)')


def downgrade() -> None:
    """Drop the core schema in reverse dependency order."""
    op.drop_table('audit_logs')
    op.drop_table('answers')
    op.drop_table('metrics')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('users')
    op.drop_table('companies')
