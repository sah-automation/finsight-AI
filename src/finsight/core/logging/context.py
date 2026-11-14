"""Request-scoped trace context variables and binding helpers."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_trace_id: ContextVar[str | None] = ContextVar('trace_id', default=None)
_company_id: ContextVar[str | None] = ContextVar('company_id', default=None)
_user_id: ContextVar[str | None] = ContextVar('user_id', default=None)
_span_name: ContextVar[str | None] = ContextVar('span_name', default=None)
_switch_values: ContextVar[dict[str, Any] | None] = ContextVar('switch_values', default=None)


def bind_request_context(
    trace_id: str | None = None,
    company_id: str | None = None,
    user_id: str | None = None,
) -> tuple[Any, Any, Any]:
    """Bind request context and return the tokens needed to reset it."""
    return (
        _trace_id.set(trace_id),
        _company_id.set(company_id),
        _user_id.set(user_id),
    )


def reset_request_context(tokens: tuple[Any, Any, Any]) -> None:
    """Restore the context captured by :func:`bind_request_context`."""
    trace_token, company_token, user_token = tokens
    _trace_id.reset(trace_token)
    _company_id.reset(company_token)
    _user_id.reset(user_token)


__all__ = ['bind_request_context', 'reset_request_context']
