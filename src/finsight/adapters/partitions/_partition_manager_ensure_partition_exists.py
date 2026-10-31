"""Auto-extracted helper for PartitionManager.ensure_partition_exists."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._partition_manager_shared import (
    _partition_name,
)

if TYPE_CHECKING:
    from finsight.core.types import (
        CompanyId,
    )


if TYPE_CHECKING:
    from .partition_manager import PartitionManager


async def _ensure_partition_exists(
    self: PartitionManager,
    company_id: CompanyId,
    table_name: str,
) -> bool:
    """Ensure partition exists (idempotent)."""
    partition_name = _partition_name(company_id, table_name)
    # Check if partition exists
    try:
        row = await self._fetch_one(
            """
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = :partition_name AND n.nspname = 'public'
            """,
            {'partition_name': partition_name},
        )
        if row is not None:
            return True
    except Exception:
        pass

    # Create if not exists
    try:
        await self.create_partition(company_id, table_name)
        return True
    except Exception:
        return False
