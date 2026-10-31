"""Auto-extracted helper for PartitionManager._fetch_one."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

from sqlalchemy import text

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .partition_manager import PartitionManager


async def _fetch_one(self: PartitionManager, sql: str, params: dict[str, Any] | None = None) -> Any:
    import inspect

    session = self._session_or_engine
    if hasattr(session, 'execute'):
        result = session.execute(text(sql), params or {})
        if inspect.isawaitable(result):
            result = await result
        fetch = getattr(result, 'fetchone', None)
        if callable(fetch):
            row = fetch()
            if inspect.isawaitable(row):
                row = await row
        else:
            row = result
        if hasattr(session, 'commit'):
            try:
                commit_result = session.commit()
                if inspect.isawaitable(commit_result):
                    await commit_result
            except Exception:
                pass
        return row
    if hasattr(session, 'begin'):
        async_cm = session.begin()
        async with async_cm as conn:
            result = conn.execute(text(sql), params or {})
            if inspect.isawaitable(result):
                result = await result
            fetch = getattr(result, 'fetchone', None)
            if callable(fetch):
                row = fetch()
                if inspect.isawaitable(row):
                    row = await row
                return row
            return result.fetchone() if hasattr(result, 'fetchone') else result
    raise TypeError('Unsupported session/engine type')
