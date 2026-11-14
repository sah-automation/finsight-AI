"""Auto-extracted helper for PartitionManager.list_partitions."""

from __future__ import annotations

import contextlib
import inspect
from typing import (
    TYPE_CHECKING,
)

from sqlalchemy import text

from ._partition_manager__execute import _commit_if_present

if TYPE_CHECKING:
    from finsight.core.types import (
        CompanyId,
    )

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .partition_manager import PartitionManager

_LIST_PARTITIONS_SQL = """
SELECT c.relname
FROM pg_inherits i
JOIN pg_class c ON c.oid = i.inhrelid
JOIN pg_class p ON p.oid = i.inhparent
JOIN pg_namespace n ON n.oid = p.relnamespace
WHERE n.nspname = 'public'
AND c.relname LIKE :pattern
"""


async def _list_partitions(
    self: PartitionManager,
    company_id: CompanyId,
) -> list[str]:
    """List all partitions for a company."""
    try:
        pattern = f'%company_{str(company_id).replace("-", "")}%'
        result = self._session_or_engine.execute(text(_LIST_PARTITIONS_SQL), {'pattern': pattern})
        if inspect.isawaitable(result):
            result = await result
        rows = result.fetchall() if hasattr(result, 'fetchall') else list(result or [])
        if inspect.isawaitable(rows):
            rows = await rows
        with contextlib.suppress(Exception):
            await _commit_if_present(self._session_or_engine)
        return [row[0] for row in rows]
    except Exception:
        return []
