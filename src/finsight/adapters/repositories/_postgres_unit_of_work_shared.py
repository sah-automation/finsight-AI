"""Shared helpers for PostgresUnitOfWork."""

from __future__ import annotations

import inspect
from typing import Any

try:
    from finsight.adapters.repositories.base_repository import set_rls_context as _set_rls_context
except ImportError:  # pragma: no cover
    _set_rls_context = None  # type: ignore[assignment]


def _looks_like_session(value: object) -> bool:
    return (
        hasattr(value, 'execute')
        or hasattr(value, 'begin')
        or hasattr(value, 'commit')
        or hasattr(value, 'rollback')
    )


async def _await_maybe(value: object) -> object:
    if inspect.isawaitable(value):
        return await value
    return value


def _resolve_session(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None or isinstance(arg, (dict, str, int, float, bool)):
            continue
        if _looks_like_session(arg):
            return arg
    for key in (
        'session',
        'db_session',
        'database_session',
        'connection',
        'engine',
        'session_or_engine',
    ):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('session_factory', 'factory'):
        value = kwargs.get(key)
        if value is not None:
            return value
    return None
