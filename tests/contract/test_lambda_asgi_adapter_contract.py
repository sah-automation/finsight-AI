"""Contract tests for the Lambda→ASGI adapter in ``entrypoints.api.main``.

API Gateway HTTP APIs route every request through this adapter, and the
application wraps its routers in ``CorrelationMiddleware`` (a Starlette
``BaseHTTPMiddleware``). Starlette's ``BaseHTTPMiddleware`` expects the ASGI
``receive()`` callable to eventually yield an ``http.disconnect`` message; the
Lambda adapter used to answer every call with ``http.request``, which made any
body-consuming POST request (``/ask``, uploads, feedback) fail with a 502.

These tests pin the adapter behavior at the real seam: a Lambda event flowing
through ``handler`` into an app wrapped in a ``BaseHTTPMiddleware``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from finsight.entrypoints.api import main as api_main

if TYPE_CHECKING:
    from starlette.requests import Request


class _CorrelationStyleMiddleware(BaseHTTPMiddleware):
    """Mimic ``CorrelationMiddleware``: dispatch → call_next passthrough."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        return await call_next(request)


async def _read_body_endpoint(request: Request) -> JSONResponse:
    """Consume the JSON body the way FastAPI does before returning 200."""
    payload = await request.body()
    return JSONResponse({'received': json.loads(payload.decode('utf-8') or '{}')})


async def _streaming_endpoint(request: Request) -> StreamingResponse:
    """Consume the body and return an SSE-style stream (like ``/ask``).

    Starlette's ``StreamingResponse`` runs ``listen_for_disconnect(receive)``
    in a task group, so the adapter's ``receive()`` must terminate with
    ``http.disconnect`` instead of returning a second ``http.request``.
    """
    payload = await request.body()
    payload_json = json.loads(payload.decode('utf-8') or '{}')

    async def _gen() -> Any:
        yield f'event: status\ndata: {json.dumps({"received": payload_json})}\n\n'.encode()
        yield b'event: complete\ndata: {"done": true}\n\n'

    return StreamingResponse(_gen(), media_type='text/event-stream')


def _middleware_app() -> Starlette:
    return Starlette(
        routes=[
            Route('/ask', _read_body_endpoint, methods=['POST']),
            Route('/stream', _streaming_endpoint, methods=['POST']),
        ],
        middleware=[Middleware(_CorrelationStyleMiddleware)],
    )


def _lambda_event(path: str, method: str, body: str) -> dict[str, Any]:
    return {
        'rawPath': path,
        'rawQueryString': '',
        'headers': {'content-type': 'application/json', 'host': 'api.test'},
        'requestContext': {'http': {'method': method, 'path': path}},
        'isBase64Encoded': False,
        'body': body,
    }


@pytest.mark.asyncio
async def test_post_with_body_passes_through_base_http_middleware(monkeypatch: Any) -> None:
    """POST with a body must survive a BaseHTTPMiddleware (regression: 502)."""
    monkeypatch.setattr(api_main, '_get_app', _middleware_app)

    def _run() -> dict[str, Any]:
        return api_main.handler(
            _lambda_event('/ask', 'POST', json.dumps({'question': 'health check'})),
            context=None,
        )

    # handler() calls asyncio.run() internally, so it must be called on a
    # thread without a running loop.
    response = await anyio.to_thread.run_sync(_run)

    assert response['statusCode'] == 200, response
    assert json.loads(response['body']) == {
        'received': {'question': 'health check'},
    }


@pytest.mark.asyncio
async def test_streaming_post_with_body_survives_middleware(monkeypatch: Any) -> None:
    """Streaming POST (SSE, like /ask) must not fail with a 502.

    Regression: the adapter's ``receive()`` answered every call with
    ``http.request``; Starlette streaming responses wait for
    ``http.disconnect`` and blew up with ``Unexpected message received``.
    """
    monkeypatch.setattr(api_main, '_get_app', _middleware_app)

    def _run() -> dict[str, Any]:
        return api_main.handler(
            _lambda_event('/stream', 'POST', json.dumps({'question': 'health check'})),
            context=None,
        )

    response = await anyio.to_thread.run_sync(_run)

    assert response['statusCode'] == 200, response
    body = response['body']
    assert 'event: status' in body
    assert 'event: complete' in body
    # Regression: response headers must be str keys/values, not bytes reprs.
    # Bytes keys (e.g. "b'content-type'") caused API Gateway to default the
    # content-type to text/plain and broke SSE clients.
    for key, value in response['headers'].items():
        assert isinstance(key, str) and not key.startswith("b'")
        assert isinstance(value, str) and not value.startswith("b'")
    assert json.loads(body.split('data: ', 1)[1].split('\n\n', 1)[0]) == {
        'received': {'question': 'health check'}
    }


@pytest.mark.asyncio
async def test_get_request_without_body_still_works(monkeypatch: Any) -> None:
    """GET requests must keep working through the adapter."""
    monkeypatch.setattr(api_main, '_get_app', _middleware_app)

    def _run() -> dict[str, Any]:
        return api_main.handler(_lambda_event('/ask', 'GET', ''), context=None)

    response = await anyio.to_thread.run_sync(_run)

    assert response['statusCode'] == 405  # route only allows POST; no 502 crash
