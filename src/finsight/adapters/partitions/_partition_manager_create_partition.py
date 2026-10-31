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


_INDEX_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    'documents': (
        ('company_status', '(company_id, status)'),
        ('company_period', '(company_id, period_start, period_end)'),
    ),
    'document_chunks': (('company_document', '(company_id, document_id)'),),
    'metrics': (('company_name_period', '(company_id, name, period_end)'),),
    'answers': (('company_created', '(company_id, created_at)'),),
    'document_versions': (
        ('company_document', '(company_id, document_id)'),
        ('company_state', '(company_id, state)'),
    ),
    'jobs': (
        ('company_status', '(company_id, status)'),
        ('company_created', '(company_id, created_at)'),
    ),
}

_DEFAULT_INDEX_COLUMNS = (('company_id', '(company_id)'),)


def _partition_index_statements(partition_name: str, table_name: str) -> list[str]:
    statements = [
        f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_{suffix} ON {partition_name} {columns}'
        for suffix, columns in _INDEX_COLUMNS.get(table_name, _DEFAULT_INDEX_COLUMNS)
    ]
    if table_name == 'document_chunks':
        statements.append(
            f'CREATE INDEX IF NOT EXISTS ix_{partition_name}_embedding_hnsw ON {partition_name} '
            'USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 200)'
        )
    return statements


async def _create_partition_table(
    self: PartitionManager,
    company_id: CompanyId,
    partition_name: str,
    table_name: str,
) -> None:
    with contextlib.suppress(Exception):
        await self._execute(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF {table_name}
            FOR VALUES IN ('{company_id}')
            """
        )


async def _create_partition_indexes(
    self: PartitionManager,
    partition_name: str,
    table_name: str,
) -> None:
    with contextlib.suppress(Exception):
        for statement in _partition_index_statements(partition_name, table_name):
            await self._execute(statement)


async def _record_partition_direct(
    self: PartitionManager,
    company_id: CompanyId,
    partition_name: str,
    table_name: str,
) -> None:
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


async def _record_created_partition(
    self: PartitionManager,
    company_id: CompanyId,
    partition_name: str,
    table_name: str,
) -> None:
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
        return
    await _record_partition_direct(self, company_id, partition_name, table_name)


async def _create_partition(
    self: PartitionManager,
    company_id: CompanyId,
    table_name: str,
) -> str:
    """Create a partition for a company on the given table."""
    partition_name = _partition_name(company_id, table_name)
    await _create_partition_table(self, company_id, partition_name, table_name)
    await _create_partition_indexes(self, partition_name, table_name)
    await _record_created_partition(self, company_id, partition_name, table_name)
    return partition_name
