"""slice 5.4: metric scope columns and hybrid-search indexes

Revision ID: 0006_slice5_4_retrieval
Revises: 0005_slice4_5_lifecycle
Create Date: 2026-10-29 00:00:00.000000

"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '0006_slice5_4_retrieval'
down_revision: str | None = '0005_slice4_5_lifecycle'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Metrics: category/version scope, a readable period label and provenance.
    op.execute('ALTER TABLE metrics ADD COLUMN IF NOT EXISTS category text')
    op.execute('ALTER TABLE metrics ADD COLUMN IF NOT EXISTS version_id text')
    op.execute('ALTER TABLE metrics ADD COLUMN IF NOT EXISTS period_label text')
    op.execute('ALTER TABLE metrics ADD COLUMN IF NOT EXISTS source_chunk_id uuid')
    op.execute('ALTER TABLE metrics ADD COLUMN IF NOT EXISTS source_location jsonb')
    # A metric can be scoped to a label such as "2025-Q1" without fake dates.
    op.execute('ALTER TABLE metrics ALTER COLUMN period_start DROP NOT NULL')
    op.execute('ALTER TABLE metrics ALTER COLUMN period_end DROP NOT NULL')
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_metrics_company_category ON metrics (company_id, category)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_metrics_company_document '
        'ON metrics (company_id, document_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_metrics_company_version ON metrics (company_id, version_id)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_metrics_company_period_label '
        'ON metrics (company_id, period_label)'
    )

    # Hybrid search: one expression index shared by every company partition.
    with contextlib.suppress(Exception):
        op.execute(
            'CREATE INDEX IF NOT EXISTS ix_document_chunks_search_vector '
            "ON document_chunks USING gin (to_tsvector('english', coalesce(content, '')))"
        )


def downgrade() -> None:
    with contextlib.suppress(Exception):
        op.execute('DROP INDEX IF EXISTS ix_document_chunks_search_vector')
    for statement in (
        'DROP INDEX IF EXISTS ix_metrics_company_period_label',
        'DROP INDEX IF EXISTS ix_metrics_company_version',
        'DROP INDEX IF EXISTS ix_metrics_company_document',
        'DROP INDEX IF EXISTS ix_metrics_company_category',
        'ALTER TABLE metrics DROP COLUMN IF EXISTS source_location',
        'ALTER TABLE metrics DROP COLUMN IF EXISTS source_chunk_id',
        'ALTER TABLE metrics DROP COLUMN IF EXISTS period_label',
        'ALTER TABLE metrics DROP COLUMN IF EXISTS version_id',
        'ALTER TABLE metrics DROP COLUMN IF EXISTS category',
    ):
        op.execute(statement)
