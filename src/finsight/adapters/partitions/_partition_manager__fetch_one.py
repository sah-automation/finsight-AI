"""Auto-extracted helper for PartitionManager._fetch_one."""

from __future__ import annotations

import contextlib
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
)

from sqlalchemy import text

from ._partition_manager__execute import _commit_if_present

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .partition_manager import PartitionManager


async def _await_fetch(fetch: Any) -> Any:
    row = fetch()
    if inspect.isawaitable(row):
        row = await row
    return row


async def _fetch_from_session(session: Any, sql: str, params: dict[str, Any]) -> Any:
    result = session.execute(text(sql), params)
    if inspect.isawaitable(result):
        result = await result
    fetch = getattr(result, 'fetchone', None)
    row = await _await_fetch(fetch) if callable(fetch) else result
    with contextlib.suppress(Exception):
        await _commit_if_present(session)
    return row


async def _fetch_from_begin(session: Any, sql: str, params: dict[str, Any]) -> Any:
    async with session.begin() as conn:
        result = conn.execute(text(sql), params)
        if inspect.isawaitable(result):
            result = await result
        fetch = getattr(result, 'fetchone', None)
        if callable(fetch):
            return await _await_fetch(fetch)
        return result.fetchone() if hasattr(result, 'fetchone') else result


async def _fetch_one(self: PartitionManager, sql: str, params: dict[str, Any] | None = None) -> Any:
    session = self._session_or_engine
    params = params or {}
    if hasattr(session, 'execute'):
        return await _fetch_from_session(session, sql, params)
    if hasattr(session, 'begin'):
        return await _fetch_from_begin(session, sql, params)
    raise TypeError('Unsupported session/engine type')
