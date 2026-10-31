"""Auto-extracted helper for PartitionManager.record_partition_metadata."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from finsight.core.types import (
    CompanyId,
    PartitionStatus,
)

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .partition_manager import PartitionManager


async def _record_partition_via_repo(
    self: PartitionManager,
    company_id: CompanyId,
    partition_name: str,
    table_name: str,
) -> bool:
    if self._metadata_repo is None:
        return False
    try:
        await self._metadata_repo.record_partition(
            company_id=company_id,
            partition_name=partition_name,
            table_name=table_name,
            status=PartitionStatus.READY,
        )
        return True
    except Exception:
        return False


async def _record_partition_metadata(
    self: PartitionManager,
    company_id: CompanyId,
    partition_name: str,
    table_name: str,
) -> None:
    """Record partition metadata."""
    if await _record_partition_via_repo(self, company_id, partition_name, table_name):
        return
    with contextlib.suppress(Exception):
        await self._execute(
            """
            INSERT INTO partition_metadata (company_id, partition_name, table_name, status)
            VALUES (:company_id, :partition_name, :table_name, 'ready')
            ON CONFLICT (company_id, table_name) DO UPDATE SET status = 'ready', updated_at = now()
            """,
            {
                'company_id': str(company_id),
                'partition_name': partition_name,
                'table_name': table_name,
            },
        )
