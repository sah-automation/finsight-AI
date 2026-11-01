"""Helpers for resolving reporter backends for tracing spans."""

from __future__ import annotations

from typing import Any

from ._tracing_config import _first


def resolve_tracing_backend(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    backend: Any = None
    for arg in args:
        if hasattr(arg, 'add_span') or hasattr(arg, 'get_spans') or hasattr(arg, 'record_span'):
            backend = arg
            break
    candidate = _first(
        kwargs,
        'backend',
        'tracing_backend',
        'tracer',
        'span_backend',
        'span_store',
        'store',
        'collector',
        'storage',
        default=None,
    )
    if candidate is not None:
        backend = candidate
    return backend


async def record_tracing_backend_span(backend: Any, span: Any, logger: Any) -> None:
    if backend is None:
        return
    adder = getattr(backend, 'add_span', None)
    if not callable(adder):
        adder = getattr(backend, 'record_span', None)
    if not callable(adder):
        adder = getattr(backend, 'record', None)
    if not callable(adder):
        return
    try:
        result = adder(span)
        if hasattr(result, '__await__'):
            await result
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug('tracing backend add_span failed: %s', exc)
