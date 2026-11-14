"""Readiness report naming an unavailable dependency (#233).

Entrypoints call health_check on ports; the adapters implement the
backend-specific probes. This keeps vendor I/O behind ports.
"""

# ruff: noqa: BLE001

from __future__ import annotations

import inspect
from typing import Any

from sqlalchemy import text

_DEPENDENCIES = ('database', 'object_storage', 'queue')


def _ok() -> dict[str, str]:
    return {'status': 'ok', 'detail': ''}


def _unavailable(detail: str) -> dict[str, str]:
    return {'status': 'unavailable', 'detail': detail}


async def _await_maybe(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _check_database(container: Any) -> dict[str, str]:
    session = getattr(container, 'session', None)
    if session is None:
        return _unavailable('not configured')

    execute = getattr(session, 'execute', None)
    if not callable(execute):
        return _unavailable('database session is not queryable')

    try:
        await _await_maybe(execute(text('SELECT 1')))
    except Exception as exc:
        return _unavailable(f'database check failed: {type(exc).__name__}')
    return _ok()


async def _check_object_storage(container: Any) -> dict[str, str]:
    storage = getattr(container, 'object_storage', None)
    if storage is None:
        return _unavailable('not configured')

    health_check = getattr(storage, 'health_check', None)
    if not callable(health_check):
        return _unavailable('storage adapter does not implement health_check')

    try:
        healthy = await _await_maybe(health_check())
    except Exception as exc:
        return _unavailable(f'object storage check failed: {type(exc).__name__}')
    return _ok() if healthy else _unavailable('object storage unreachable')


async def _check_queue(container: Any) -> dict[str, str]:
    queue = getattr(container, 'queue', None)
    if queue is None:
        return _unavailable('not configured')

    health_check = getattr(queue, 'health_check', None)
    if not callable(health_check):
        return _unavailable('queue adapter does not implement health_check')

    try:
        healthy = await _await_maybe(health_check())
    except Exception as exc:
        return _unavailable(f'queue check failed: {type(exc).__name__}')
    return _ok() if healthy else _unavailable('queue unreachable')


async def build_readiness_report(container: Any) -> dict[str, Any]:
    """Probe each dependency and report the ones that are unavailable."""
    checks = {
        'database': await _check_database(container),
        'object_storage': await _check_object_storage(container),
        'queue': await _check_queue(container),
    }
    failing = [name for name in _DEPENDENCIES if checks[name]['status'] != 'ok']
    return {
        'ready': not failing,
        'checks': checks,
        'failing': failing,
    }


__all__ = ['build_readiness_report']
