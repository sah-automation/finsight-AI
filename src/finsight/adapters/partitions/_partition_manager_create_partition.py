"""Auto-extracted helper for PartitionManager.create_partition."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from finsight.core.types import (
    CompanyId,
    PartitionStatus,
)

# Host module-level definitions (injected at runtime of this helper)
from ._partition_manager_shared import (
    _partition_name,
)

if TYPE_CHECKING:
    from .partition_manager import PartitionManager


async def _create_partition(
    self: PartitionManager,
    company_id: CompanyId,
    table_name: str,
) -> str:
    """Create a partition for a company on the given table."""
    partition_name = _partition_name(company_id, table_name)
    try:
        # Create partition (bound value must be a literal in PostgreSQL)
        await self._execute(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF {table_name}
            FOR VALUES IN ('{company_id}')
            """
        )
    except Exception:
        # Partition may already exist; ignore.
        pass

    # Create indexes on partition
    try:
        if table_name == 'documents':
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_status ON {partition_name} (company_id, status)'
            )
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_period ON {partition_name} (company_id, period_start, period_end)'
            )
        elif table_name == 'document_chunks':
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_document ON {partition_name} (company_id, document_id)'
            )
            # Create HNSW vector index on partition if embedding exists
            with contextlib.suppress(Exception):
                await self._execute(
                    f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_embedding_hnsw ON {partition_name} USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200)'
                )
        elif table_name == 'metrics':
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_name_period ON {partition_name} (company_id, name, period_end)'
            )
        elif table_name == 'answers':
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_created ON {partition_name} (company_id, created_at)'
            )
        elif table_name == 'document_versions':
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_document ON {partition_name} (company_id, document_id)'
            )
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_state ON {partition_name} (company_id, state)'
            )
        elif table_name == 'jobs':
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_status ON {partition_name} (company_id, status)'
            )
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_created ON {partition_name} (company_id, created_at)'
            )
        elif table_name == 'audit_logs':
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_id ON {partition_name} (company_id)'
            )
        else:
            await self._execute(
                f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_company_id ON {partition_name} (company_id)'
            )
    except Exception:
        pass

    # Record partition metadata
    if self._metadata_repo is not None:
        try:
            await self._metadata_repo.record_partition(
                company_id=company_id,
                partition_name=partition_name,
                table_name=table_name,
                status=PartitionStatus.CREATING,
            )
            with contextlib.suppress(Exception):
                await self._metadata_repo.update_status(
                    company_id, table_name, PartitionStatus.READY
                )
        except Exception:
            pass
    else:
        # Try to record directly if no repo provided
        try:
            await self._execute(
                """
                INSERT INTO partition_metadata (company_id, partition_name, table_name, status)
                VALUES (:company_id, :partition_name, :table_name, 'creating')
                ON CONFLICT (company_id, table_name) DO NOTHING
                """,
                {
                    'company_id': str(company_id),
                    'partition_name': partition_name,
                    'table_name': table_name,
                },
            )
            with contextlib.suppress(Exception):
                await self._execute(
                    """
                    UPDATE partition_metadata
                    SET status = 'ready', updated_at = now()
                    WHERE company_id = :company_id AND table_name = :table_name
                    """,
                    {'company_id': str(company_id), 'table_name': table_name},
                )
        except Exception:
            pass

    return partition_name
