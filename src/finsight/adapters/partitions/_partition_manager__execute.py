"""Auto-extracted helper for PartitionManager._execute."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

from sqlalchemy import text

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .partition_manager import PartitionManager


async def _execute(self: PartitionManager, sql: str, params: dict[str, Any] | None = None) -> None:
    import inspect

    session = self._session_or_engine
    # Support different session/engine patterns
    if hasattr(session, 'execute'):
        # Could be AsyncSession or Connection (sync or async)
        try:
            result = session.execute(text(sql), params or {})
            if inspect.isawaitable(result):
                result = await result
            # Try to commit if it's a session
            if hasattr(session, 'commit'):
                try:
                    commit_result = session.commit()
                    if inspect.isawaitable(commit_result):
                        await commit_result
                except Exception:
                    pass
            return
        except Exception:
            # Reset any aborted transaction so later calls can proceed.
            if hasattr(session, 'rollback'):
                try:
                    rollback_result = session.rollback()
                    if inspect.isawaitable(rollback_result):
                        await rollback_result
                except Exception:
                    pass
            raise
    # Try getting a connection
    if hasattr(session, 'begin'):
        try:
            async_cm = session.begin()
            async with async_cm as conn:
                result = conn.execute(text(sql), params or {})
                if inspect.isawaitable(result):
                    await result
            return
        except Exception:
            raise
    raise TypeError('Unsupported session/engine type')
