# ruff: noqa: PLR0913, PLR0917

"""Correlation middleware for FinSight HTTP requests.

The middleware is the API boundary seam for observability: it assigns or
propagates ``X-Request-ID``, binds request-scoped logging context, and emits
one ``http_request`` root span for every request.
"""

from __future__ import annotations

import contextlib
import inspect
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware

from finsight.core.logging.context import bind_request_context, reset_request_context
from finsight.entrypoints.api.correlation_identity import extract_identity

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

_LOGGER = logging.getLogger(__name__)
_HEADER_REQUEST_ID = 'x-request-id'
_ROOT_OPERATION = 'http_request'


def _resolve_tracing(request: Request, middleware: CorrelationMiddleware) -> Any:
    if middleware.tracing is not None:
        return middleware.tracing
    state = getattr(getattr(request, 'app', None), 'state', None)
    if state is None:
        return None
    container = getattr(state, 'container', None)
    if container is not None:
        tracing = getattr(container, 'tracing', None) or getattr(container, 'tracer', None)
        if tracing is not None:
            return tracing
    return getattr(state, 'tracing', None) or getattr(state, 'tracer', None)


def _route_for(request: Request) -> str:
    route = (getattr(request, 'scope', {}) or {}).get('route')
    return getattr(route, 'path', None) or request.url.path


def _build_attributes(
    route: str,
    method: str,
    status_code: int,
    duration_ms: float,
    user_id: Any,
    role: Any,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        'route': route,
        'method': method,
        'http_method': method,
        'status_code': status_code,
        'http_status_code': status_code,
        'duration': duration_ms,
        'duration_ms': duration_ms,
    }
    if user_id is not None:
        attributes['user_id'] = str(user_id)
    if role is not None:
        attributes['role'] = str(role)
    return attributes


async def _emit_root_span(
    tracing: Any,
    company_id: Any,
    request_id: str,
    attributes: dict[str, Any],
) -> None:
    if tracing is None:
        return
    try:
        result = tracing.start_span(
            company_id,
            _ROOT_OPERATION,
            trace_id=request_id,
            attributes=attributes,
        )
        if inspect.isawaitable(result):
            await result
    except Exception:
        _LOGGER.warning('Failed to emit %s span', _ROOT_OPERATION, exc_info=True)


async def _finalize(
    tracing: Any,
    request: Request,
    request_id: str,
    company_id: Any,
    user_id: Any,
    role: Any,
    status_code: int,
    started: float,
    response: Response | None,
) -> None:
    duration_ms = (time.perf_counter() - started) * 1000.0
    if response is not None:
        with contextlib.suppress(Exception):
            response.headers[_HEADER_REQUEST_ID] = request_id
    await _emit_root_span(
        tracing,
        company_id,
        request_id,
        _build_attributes(
            _route_for(request),
            request.method,
            status_code,
            duration_ms,
            user_id,
            role,
        ),
    )


async def _finalize_and_log(
    tracing: Any,
    request: Request,
    request_id: str,
    company_id: Any,
    user_id: Any,
    role: Any,
    status_code: int,
    started: float,
    response: Response | None,
) -> None:
    try:
        await _finalize(
            tracing,
            request,
            request_id,
            company_id,
            user_id,
            role,
            status_code,
            started,
            response,
        )
    except Exception:
        _LOGGER.exception('Failed to finalize request %s', request_id)
        raise


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Bind request context and emit one root span per HTTP request."""

    def __init__(
        self,
        app: Any,
        tracing: Any = None,
        tracer: Any = None,
        container: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(app)
        resolved = tracing if tracing is not None else tracer
        if resolved is None and container is not None:
            resolved = getattr(container, 'tracing', None) or getattr(container, 'tracer', None)
        for key in ('tracing_port', 'span_tracer', 'span_tracing', 'tracing_adapter'):
            if resolved is None and kwargs.get(key) is not None:
                resolved = kwargs[key]
        self.tracing = resolved

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        return await _dispatch_request(self, request, call_next)


async def _dispatch_request(
    middleware: CorrelationMiddleware,
    request: Request,
    call_next: Any,
) -> Response:
    request_id = str(request.headers.get(_HEADER_REQUEST_ID) or uuid.uuid4())
    company_id, user_id, role = extract_identity(request)

    context_tokens = bind_request_context(
        request_id,
        None if company_id is None else str(company_id),
        None if user_id is None else str(user_id),
    )
    tracing = _resolve_tracing(request, middleware)
    started = time.perf_counter()
    response: Response | None = None

    try:
        response = await call_next(request)
        status_code = getattr(response, 'status_code', 200)
    except Exception:
        await _finalize_and_log(
            tracing,
            request,
            request_id,
            company_id,
            user_id,
            role,
            500,
            started,
            None,
        )
        raise
    else:
        await _finalize_and_log(
            tracing,
            request,
            request_id,
            company_id,
            user_id,
            role,
            status_code,
            started,
            response,
        )
        return response
    finally:
        reset_request_context(context_tokens)


__all__ = ['CorrelationMiddleware', 'extract_identity']
