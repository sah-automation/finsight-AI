"""add partition metadata

Revision ID: 0002_partition_metadata
Revises: 0001_initial_schema
Create Date: 2026-10-27 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '0002_partition_metadata'
down_revision: str | None = '0001_initial_schema'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create partition metadata table."""
    op.execute(
        """
        CREATE TABLE partition_metadata (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            partition_name text NOT NULL,
            table_name text NOT NULL,
            status text NOT NULL DEFAULT 'creating'
                CHECK (status IN ('creating', 'ready', 'failed')),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_partition_metadata_company_table UNIQUE (company_id, table_name)
        )
        """
    )
    op.execute('CREATE INDEX ix_partition_metadata_company_id ON partition_metadata (company_id)')
    op.execute('CREATE INDEX ix_partition_metadata_status ON partition_metadata (status)')


def downgrade() -> None:
    """Drop partition metadata table."""
    op.drop_table('partition_metadata')
