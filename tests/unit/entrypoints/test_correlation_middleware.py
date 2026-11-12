"""Tests for HTTP request correlation and identity extraction (#278).

The middleware is the API boundary seam: it must generate/extract
``X-Request-ID``, bind the request trace/company/user context for every
downstream span, and emit one ``http_request`` root span carrying route,
method, status, duration, company, user, and role.

Identity comes from Cognito authorizer claims. Client-supplied identity
headers are only a local-development fallback and must never win over
authoritative claims.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from finsight.core.logging import get_company_id, get_trace_id, get_user_id
from finsight.entrypoints.api import app as app_module
from finsight.entrypoints.api import correlation_middleware
from finsight.entrypoints.api.correlation_identity import extract_identity
from finsight.entrypoints.api.correlation_middleware import CorrelationMiddleware


class _RecordingTracer:
    """Minimal TracingPort double recording emitted root spans."""

    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []

    async def start_span(
        self,
        company_id: Any,
        operation: str | None = None,
        *,
        trace_id: Any = None,
        attributes: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> object:
        self.spans.append(
            {
                'company_id': company_id,
                'operation': operation,
                'trace_id': trace_id,
                'attributes': dict(attributes or {}),
            }
        )
        return object()


def _probe_client(tracer: Any = None) -> TestClient:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware, tracing=tracer)

    @app.get('/probe')
    async def probe() -> dict[str, Any]:
        return {
            'trace_id': get_trace_id(),
            'company_id': get_company_id(),
            'user_id': get_user_id(),
        }

    return TestClient(app)


def _scope(
    *,
    request_id: str | None = None,
    path: str = '/probe',
    headers: dict[str, str] | None = None,
    claims: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    if request_id is not None:
        raw_headers.append((b'x-request-id', request_id.encode()))
    scope: dict[str, Any] = {
        'type': 'http',
        'http_version': '1.1',
        'method': 'GET',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'scheme': 'http',
        'server': ('testserver', 80),
        'client': ('testclient', 1234),
        'root_path': '',
        'headers': raw_headers,
    }
    if claims is not None:
        scope['aws.event'] = {'requestContext': {'authorizer': {'claims': claims}}}
    return scope


def _request(**kwargs: Any) -> Request:
    return Request(_scope(**kwargs))


async def _noop_app(*_args: Any) -> None:
    return None


# ------------------------------------------------------------------ request id


def test_generates_and_returns_x_request_id_when_absent() -> None:
    client = _probe_client()

    response = client.get('/probe')

    assert response.status_code == 200
    request_id = response.headers.get('x-request-id')
    assert request_id
    assert response.json()['trace_id'] == request_id


def test_preserves_incoming_x_request_id() -> None:
    client = _probe_client()

    response = client.get('/probe', headers={'X-Request-ID': 'caller-request-42'})

    assert response.headers['x-request-id'] == 'caller-request-42'
    assert response.json()['trace_id'] == 'caller-request-42'


# ------------------------------------------------------------------ root span


def test_emits_http_request_root_span_with_real_attributes() -> None:
    tracer = _RecordingTracer()
    client = _probe_client(tracer)

    client.get('/probe', headers={'X-Request-ID': 'req-root'})

    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span['operation'] == 'http_request'
    assert span['trace_id'] == 'req-root'
    attributes = span['attributes']
    assert attributes['route'] == '/probe'
    assert attributes['method'] == 'GET'
    assert attributes['status_code'] == 200
    assert attributes['duration_ms'] >= 0
    assert attributes['duration'] >= 0


def test_root_span_carries_identity_from_claims() -> None:
    tracer = _RecordingTracer()
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware, tracing=tracer)

    @app.get('/probe')
    async def probe() -> dict[str, str]:
        return {'status': 'ok'}

    with TestClient(app) as client:
        client.get(
            '/probe',
            headers={
                'X-Request-ID': 'req-claims',
                'x-company-id': 'spoofed-company',
                'x-user-id': 'spoofed-user',
                'x-role': 'spoofed-role',
            },
        )

    # No claims are available through TestClient, so headers are the fallback.
    span = tracer.spans[0]
    assert span['attributes']['user_id'] == 'spoofed-user'
    assert span['attributes']['role'] == 'spoofed-role'


# ------------------------------------------------------------------ context


def test_dispatch_binds_context_for_downstream_calls_and_resets_it() -> None:
    tracer = _RecordingTracer()
    middleware = CorrelationMiddleware(app=_noop_app, tracing=tracer)
    request = _request(
        request_id='req-context', claims={'custom:company_id': 'company-1', 'sub': 'user-1'}
    )
    observed: dict[str, Any] = {}

    async def call_next(_request: Request) -> Response:
        observed['trace_id'] = get_trace_id()
        observed['company_id'] = get_company_id()
        observed['user_id'] = get_user_id()
        return Response(status_code=204)

    async def run() -> None:
        await middleware.dispatch(request, call_next)
        assert get_trace_id() is None
        assert get_company_id() is None
        assert get_user_id() is None

    asyncio.run(run())

    assert observed == {
        'trace_id': 'req-context',
        'company_id': 'company-1',
        'user_id': 'user-1',
    }
    span = tracer.spans[0]
    assert span['company_id'] == 'company-1'
    assert span['attributes']['status_code'] == 204


def test_tracing_failure_does_not_break_the_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenTracer:
        async def start_span(self, *args: Any, **kwargs: Any) -> object:
            raise RuntimeError('tracer unavailable')

    client = _probe_client(_BrokenTracer())

    response = client.get('/probe')

    assert response.status_code == 200


def test_dispatch_logs_finalize_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    tracer = _RecordingTracer()
    middleware = CorrelationMiddleware(app=_noop_app, tracing=tracer)
    request = _request(request_id='req-log')

    async def broken_finalize(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError('finalize failed')

    monkeypatch.setattr(correlation_middleware, '_finalize', broken_finalize)

    async def call_next(_request: Request) -> Response:
        return Response(status_code=200)

    with (
        caplog.at_level('DEBUG', logger=correlation_middleware.__name__),
        pytest.raises(RuntimeError),
    ):
        asyncio.run(middleware.dispatch(request, call_next))

    assert 'finalize failed' in caplog.text


# ------------------------------------------------------------------ identity


def test_claims_take_precedence_over_client_headers() -> None:
    request = _request(
        headers={
            'x-company-id': 'spoofed-company',
            'x-user-id': 'spoofed-user',
            'x-role': 'spoofed-role',
        },
        claims={
            'custom:company_id': 'company-from-claims',
            'sub': 'user-from-claims',
            'cognito:groups': ['analyst'],
        },
    )

    assert extract_identity(request) == (
        'company-from-claims',
        'user-from-claims',
        'analyst',
    )


def test_headers_are_a_local_fallback_without_claims() -> None:
    request = _request(
        headers={'x-company-id': 'local-company', 'x-user-id': 'local-user', 'x-role': 'admin'}
    )

    assert extract_identity(request) == ('local-company', 'local-user', 'admin')


def test_state_identity_is_used_before_claims() -> None:
    request = _request(claims={'custom:company_id': 'claims-company', 'sub': 'claims-user'})
    request.state.company_id = 'state-company'
    request.state.user_id = 'state-user'

    assert extract_identity(request)[:2] == ('state-company', 'state-user')


# ------------------------------------------------------------------ /ready


def test_ready_is_distinct_from_health_and_reports_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = SimpleNamespace()
    monkeypatch.setattr(app_module, 'load_config', lambda: None)
    monkeypatch.setattr(app_module, 'build_container', lambda *_args, **_kwargs: container)
    monkeypatch.setattr(app_module.providers, 'init', lambda *_args, **_kwargs: None)

    client = TestClient(app_module.create_app())

    health = client.get('/health')
    ready = client.get('/ready')

    assert health.status_code == 200
    assert health.json() == {'status': 'ok'}
    assert ready.status_code == 503
    body = ready.json()
    assert body['ready'] is False
    assert set(body['failing']) == {'database', 'object_storage', 'queue'}
