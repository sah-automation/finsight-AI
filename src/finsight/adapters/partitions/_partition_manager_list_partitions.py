"""Auto-extracted helper for PartitionManager.list_partitions."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

from sqlalchemy import text

if TYPE_CHECKING:
    from finsight.core.types import (
        CompanyId,
    )

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .partition_manager import PartitionManager


async def _list_partitions(
    self: PartitionManager,
    company_id: CompanyId,
) -> list[str]:
    """List all partitions for a company."""
    try:
        import inspect

        # Look for partitions matching pattern
        result = self._session_or_engine.execute(
            text(
                """
                SELECT c.relname
                FROM pg_inherits i
                JOIN pg_class c ON c.oid = i.inhrelid
                JOIN pg_class p ON p.oid = i.inhparent
                JOIN pg_namespace n ON n.oid = p.relnamespace
                WHERE n.nspname = 'public'
                AND c.relname LIKE :pattern
                """
            ),
            {'pattern': f'%company_{str(company_id).replace("-", "")}%'},
        )
        if inspect.isawaitable(result):
            result = await result
        rows = result.fetchall() if hasattr(result, 'fetchall') else list(result or [])
        if inspect.isawaitable(rows):
            rows = await rows
        if hasattr(self._session_or_engine, 'commit'):
            try:
                commit_result = self._session_or_engine.commit()
                if inspect.isawaitable(commit_result):
                    await commit_result
            except Exception:
                pass
        return [row[0] for row in rows]
    except Exception:
        return []
