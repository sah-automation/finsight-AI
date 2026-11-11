# ruff: noqa: BLE001, S110, PLR0913, PLR0917

"""Correlation middleware for FinSight HTTP requests."""

from __future__ import annotations

import contextlib
import inspect
import time
import uuid
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware

from finsight.core.logging import (
    _company_id,
    _trace_id,
    _user_id,
)
from finsight.entrypoints.api.correlation_identity import _extract_identity as extract_identity

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

_HEADER_REQUEST_ID = 'x-request-id'


def _resolve_tracing(request: Request, self: Any) -> Any:
    tracing = getattr(self, 'tracing', None)
    if tracing is None:
        tracing = getattr(self, 'tracer', None)
    if tracing is None:
        container = getattr(self, 'container', None)
        if container is not None:
            tracing = getattr(container, 'tracing', None) or getattr(container, 'tracer', None)
    if tracing is None:
        app_state = getattr(getattr(request, 'app', None), 'state', None)
        if app_state is not None:
            container = getattr(app_state, 'container', None)
            if container is not None:
                tracing = getattr(container, 'tracing', None) or getattr(container, 'tracer', None)
            if tracing is None:
                tracing = getattr(app_state, 'tracing', None) or getattr(app_state, 'tracer', None)
    return tracing


def _route_for(request: Request) -> Any:
    route_obj = (getattr(request, 'scope', {}) or {}).get('route')
    if route_obj is not None:
        path = getattr(route_obj, 'path', None)
        if path is not None:
            return path
    return request.url.path


def _build_attributes(
    route: Any,
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


async def _call_tracer(
    tracing: Any,
    company_id: Any,
    request_id: str,
    attributes: dict[str, Any],
) -> None:
    method = _tracer_method(tracing)
    if method is None:
        return
    kwargs = _tracer_kwargs(method, request_id, attributes)
    try:
        result = method(company_id, 'http_request', **kwargs)
    except TypeError:
        try:
            result = method(company_id, 'http_request', attributes=attributes)
        except TypeError:
            try:
                result = method(company_id, 'http_request')
            except TypeError:
                result = method(company_id, operation='http_request')
    if result is not None and hasattr(result, '__await__'):
        await result


def _tracer_method(tracing: Any) -> Any:
    for name in (
        'start_span',
        'span',
        'emit_span',
        'trace',
        'trace_operation',
        'record_span',
        'emit',
        'record',
        'begin_span',
        'open_span',
        'create_span',
    ):
        candidate = getattr(tracing, name, None)
        if callable(candidate):
            return candidate
    return None


def _tracer_kwargs(method: Any, request_id: str, attributes: dict[str, Any]) -> dict[str, Any]:
    try:
        sig = inspect.signature(method)
        accepts_attrs = 'attributes' in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        accepts_trace = 'trace_id' in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
    except (TypeError, ValueError):
        accepts_attrs = True
        accepts_trace = True
    kwargs: dict[str, Any] = {}
    if accepts_trace:
        kwargs['trace_id'] = request_id
    if accepts_attrs:
        kwargs['attributes'] = attributes
    try:
        param_names = set(inspect.signature(method).parameters.keys())
    except (TypeError, ValueError):
        param_names = set()
    if 'name' in param_names:
        kwargs['name'] = 'http_request'
    if 'span_name' in param_names:
        kwargs['span_name'] = 'http_request'
    return kwargs


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
    trace_token: Any,
    company_token: Any,
    user_token: Any,
) -> None:
    duration_ms = (time.perf_counter() - started) * 1000.0
    if response is not None:
        with contextlib.suppress(Exception):
            response.headers[_HEADER_REQUEST_ID] = request_id
    try:
        await _call_tracer(
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
    except Exception:
        pass
    finally:
        _trace_id.reset(trace_token)
        _company_id.reset(company_token)
        _user_id.reset(user_token)


class CorrelationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        tracing: Any = None,
        tracer: Any = None,
        container: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(app)
        self.tracing = tracing if tracing is not None else tracer
        self.tracer = self.tracing
        self.container = container
        if self.tracing is None and container is not None:
            self.tracing = getattr(container, 'tracing', None) or getattr(container, 'tracer', None)
            self.tracer = self.tracing
        if self.tracing is None:
            for key in ('tracing_port', 'span_tracer', 'span_tracing', 'tracing_adapter'):
                value = kwargs.get(key)
                if value is not None:
                    self.tracing = value
                    self.tracer = value
                    break

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        return await _dispatch_request(self, request, call_next)


async def _dispatch_request(self_obj: Any, request: Request, call_next: Any) -> Response:
    request_id = request.headers.get(_HEADER_REQUEST_ID)
    if not request_id:
        request_id = str(uuid.uuid4())
    request_id = str(request_id)

    company_id, user_id, role = extract_identity(request)

    trace_token = _trace_id.set(request_id)
    company_token = _company_id.set(None if company_id is None else str(company_id))
    user_token = _user_id.set(None if user_id is None else str(user_id))

    tracing = _resolve_tracing(request, self_obj)

    started = time.perf_counter()
    status_code = 500
    response: Response | None = None
    try:
        response = await call_next(request)
        status_code = getattr(response, 'status_code', 200)
    except Exception:
        status_code = 500
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
            trace_token,
            company_token,
            user_token,
        )
        raise
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
        trace_token,
        company_token,
        user_token,
    )
    return response


__all__ = ['CorrelationMiddleware', 'extract_identity']
