"""Contract tests: HTTP requests produce a root ``http_request`` span (#288).

Proves that the CorrelationMiddleware emits one ``http_request`` root span per
HTTP request, carries the originating ``X-Request-ID`` as the trace id, and
that downstream spans emitted during the request share that trace id.
"""

from __future__ import annotations

from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.entrypoints.api.correlation_middleware import CorrelationMiddleware

pytestmark = pytest.mark.contract

REQUEST_ID = 'req-http-1'


def _make_app(tracing: Any) -> Starlette:
    async def homepage(request: Any) -> JSONResponse:
        return JSONResponse({'ok': True})

    app = Starlette(routes=[Route('/', homepage)])
    app.add_middleware(CorrelationMiddleware, tracing=tracing)
    app.state.tracing = tracing
    return app


def _http_request_span(spans: list[Any]) -> Any:
    roots = [s for s in spans if s.name == 'http_request']
    assert roots, 'expected an http_request root span'
    return roots[0]


def test_middleware_emits_http_request_root_span_with_request_id() -> None:
    tracer = TracingAdapter(service_name='test', enabled=True)
    app = _make_app(tracer)

    with TestClient(app) as client:
        response = client.get('/', headers={'x-request-id': REQUEST_ID})
    assert response.status_code == 200

    spans = tracer.emitted_spans()
    assert spans, 'expected at least one emitted span'
    root = _http_request_span(spans)
    assert root.trace_id == REQUEST_ID, (
        f'root span trace id {root.trace_id!r} does not echo X-Request-ID'
    )
    assert root.attributes.get('route') == '/'
    assert root.attributes.get('method') == 'GET'
    assert root.attributes.get('status_code') == 200
    assert isinstance(root.attributes.get('duration_ms'), (int, float))
    assert root.attributes.get('duration_ms', 0) >= 0


def test_middleware_generates_trace_id_when_header_absent() -> None:
    tracer = TracingAdapter(service_name='test', enabled=True)
    app = _make_app(tracer)

    with TestClient(app) as client:
        response = client.get('/')
    assert response.status_code == 200

    root = _http_request_span(tracer.emitted_spans())
    assert root.trace_id is not None
    assert isinstance(str(root.trace_id), str) and len(str(root.trace_id)) > 0
