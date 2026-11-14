"""Auto-extracted helper for PartitionManager._execute."""

from __future__ import annotations

import contextlib
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
)

from sqlalchemy import text

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .partition_manager import PartitionManager


async def _commit_if_present(session: Any) -> None:
    if not hasattr(session, 'commit'):
        return
    commit_result = session.commit()
    if inspect.isawaitable(commit_result):
        await commit_result


async def _rollback_quietly(session: Any) -> None:
    if not hasattr(session, 'rollback'):
        return
    with contextlib.suppress(Exception):
        rollback_result = session.rollback()
        if inspect.isawaitable(rollback_result):
            await rollback_result


async def _execute_with_session(session: Any, sql: str, params: dict[str, Any]) -> None:
    try:
        result = session.execute(text(sql), params)
        if inspect.isawaitable(result):
            result = await result
        with contextlib.suppress(Exception):
            await _commit_if_present(session)
    except Exception:
        await _rollback_quietly(session)
        raise


async def _execute_on_begin(session: Any, sql: str, params: dict[str, Any]) -> None:
    async with session.begin() as conn:
        result = conn.execute(text(sql), params)
        if inspect.isawaitable(result):
            await result


async def _execute(self: PartitionManager, sql: str, params: dict[str, Any] | None = None) -> None:
    session = self._session_or_engine
    params = params or {}
    if hasattr(session, 'execute'):
        await _execute_with_session(session, sql, params)
        return
    if hasattr(session, 'begin'):
        await _execute_on_begin(session, sql, params)
        return
    raise TypeError('Unsupported session/engine type')
