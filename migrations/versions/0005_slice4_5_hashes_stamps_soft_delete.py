"""slice 4.5: page hashes, hashes/stable ids, flags, stamps, soft delete, supersession

Revision ID: 0005_slice4_5_lifecycle
Revises: 0004_jobs_document_versions
Create Date: 2026-10-29 00:00:00.000000

"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '0005_slice4_5_lifecycle'
down_revision: str | None = '0004_jobs_document_versions'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Documents: soft delete, category/period, stamps, audit and page hashes.
    op.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS period text')
    op.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS category text')
    op.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_stamp text')
    op.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS page_hashes jsonb')
    op.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS deleted_at timestamptz')
    op.execute(
        'ALTER TABLE documents ADD COLUMN IF NOT EXISTS deleted_by uuid '
        'REFERENCES users (id) ON DELETE SET NULL'
    )
    op.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS deleted_reason text')
    op.execute('ALTER TABLE documents ADD COLUMN IF NOT EXISTS deleted_retention_days integer')
    op.execute(
        'ALTER TABLE documents ADD COLUMN IF NOT EXISTS created_by uuid '
        'REFERENCES users (id) ON DELETE SET NULL'
    )
    op.execute(
        'ALTER TABLE documents ADD COLUMN IF NOT EXISTS updated_by uuid '
        'REFERENCES users (id) ON DELETE SET NULL'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_documents_company_deleted_at '
        'ON documents (company_id, deleted_at)'
    )

    # Document versions: stamp, supersession tracking, page hashes, audit.
    op.execute('ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS document_stamp text')
    op.execute('ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS page_hashes jsonb')
    op.execute('ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS superseded_by uuid')
    op.execute('ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS superseded_at timestamptz')
    op.execute('ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS supersession_reason text')
    op.execute(
        'ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS created_by uuid '
        'REFERENCES users (id) ON DELETE SET NULL'
    )
    op.execute(
        'ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS updated_by uuid '
        'REFERENCES users (id) ON DELETE SET NULL'
    )
    op.execute(
        'ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS '
        'is_active boolean NOT NULL DEFAULT TRUE'
    )

    # Document chunks: stable ids, hashes, active flag and lifecycle columns.
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunk_id text')
    op.execute('UPDATE document_chunks SET chunk_id = COALESCE(chunk_id, id::text)')
    op.execute('ALTER TABLE document_chunks ALTER COLUMN chunk_id SET NOT NULL')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS version_id text')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS parent_chunk_id uuid')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS content_hash text')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunk_hash text')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_number integer')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_hash text')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS structure_path jsonb')
    op.execute(
        'ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS ordinal integer NOT NULL DEFAULT 0'
    )
    op.execute(
        'ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS '
        'is_parent boolean NOT NULL DEFAULT FALSE'
    )
    op.execute(
        'ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS '
        'is_active boolean NOT NULL DEFAULT TRUE'
    )
    op.execute(
        'ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS '
        'needs_review boolean NOT NULL DEFAULT FALSE'
    )
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS context_header text')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_model_version text')
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS metadata jsonb')
    op.execute(
        'ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS '
        'updated_at timestamptz NOT NULL DEFAULT now()'
    )
    op.execute('ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS version_id_alias text')
    op.execute(
        'UPDATE document_chunks SET version_id_alias = COALESCE(version_id_alias, version_id)'
    )

    with contextlib.suppress(Exception):
        op.execute(
            'ALTER TABLE document_chunks ADD CONSTRAINT uq_document_chunks_company_chunk_id '
            'UNIQUE (company_id, chunk_id)'
        )


def downgrade() -> None:
    with contextlib.suppress(Exception):
        op.execute(
            'ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS '
            'uq_document_chunks_company_chunk_id'
        )
    for stmt in (
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS updated_at',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS metadata',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_model_version',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS context_header',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS needs_review',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS is_active',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS is_parent',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS ordinal',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS structure_path',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS page_hash',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS page_number',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS chunk_hash',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_hash',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS parent_chunk_id',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS version_id_alias',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS version_id',
        'ALTER TABLE document_chunks DROP COLUMN IF EXISTS chunk_id',
        'ALTER TABLE document_versions DROP COLUMN IF EXISTS is_active',
        'ALTER TABLE document_versions DROP COLUMN IF EXISTS updated_by',
        'ALTER TABLE document_versions DROP COLUMN IF EXISTS created_by',
        'ALTER TABLE document_versions DROP COLUMN IF EXISTS supersession_reason',
        'ALTER TABLE document_versions DROP COLUMN IF EXISTS superseded_at',
        'ALTER TABLE document_versions DROP COLUMN IF EXISTS superseded_by',
        'ALTER TABLE document_versions DROP COLUMN IF EXISTS page_hashes',
        'ALTER TABLE document_versions DROP COLUMN IF EXISTS document_stamp',
        'ALTER TABLE documents DROP COLUMN IF EXISTS updated_by',
        'ALTER TABLE documents DROP COLUMN IF EXISTS created_by',
        'ALTER TABLE documents DROP COLUMN IF EXISTS deleted_retention_days',
        'ALTER TABLE documents DROP COLUMN IF EXISTS deleted_reason',
        'ALTER TABLE documents DROP COLUMN IF EXISTS deleted_by',
        'ALTER TABLE documents DROP COLUMN IF EXISTS deleted_at',
        'ALTER TABLE documents DROP COLUMN IF EXISTS page_hashes',
        'ALTER TABLE documents DROP COLUMN IF EXISTS document_stamp',
        'ALTER TABLE documents DROP COLUMN IF EXISTS category',
        'ALTER TABLE documents DROP COLUMN IF EXISTS period',
    ):
        op.execute(stmt)
