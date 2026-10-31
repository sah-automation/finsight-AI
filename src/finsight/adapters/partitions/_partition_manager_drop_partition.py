"""Auto-extracted helper for PartitionManager.drop_partition."""

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


async def _drop_partition(
    self: PartitionManager,
    company_id: CompanyId,
    table_name: str,
) -> bool:
    """Drop a partition for a company."""
    partition_name = _partition_name(company_id, table_name)
    try:
        await self._execute(f'DROP TABLE IF EXISTS {partition_name} CASCADE')
        return True
    except Exception:
        return False
