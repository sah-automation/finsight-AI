"""ASGI entrypoint for the FinSight API (deployment/public surface).

Exposes ``create_app`` and a lazily-built ``app`` for ``uvicorn``. The app is
built on first attribute access so importing this module has no wiring side
effects. Retained because the CDK handler references this module. Owner:
platform; removal condition: none.

``handler`` is the AWS Lambda entrypoint declared by the CDK compute stack
(``finsight.entrypoints.api.main.handler``). It adapts API Gateway events to
the ASGI application and returns a Lambda-compatible response dictionary.
"""

from __future__ import annotations

import asyncio
import base64
import json
from functools import cache
from typing import Any
from urllib.parse import urlencode

from finsight.entrypoints.api.app import create_app

__all__ = ['create_app', 'handler']


@cache
def _get_app() -> Any:
    """Build and cache the ASGI application once."""
    return create_app()


def _is_base64(event: dict[str, Any]) -> bool:
    return bool(event.get('isBase64Encoded'))


def _raw_body(event: dict[str, Any]) -> bytes:
    body = event.get('body')
    if body is None:
        return b''
    if isinstance(body, bytes):
        return body
    text = str(body)
    if _is_base64(event):
        return base64.b64decode(text)
    return text.encode('utf-8')


def _headers(event: dict[str, Any]) -> list[tuple[bytes, bytes]]:
    headers = event.get('headers') or {}
    multi = event.get('multiValueHeaders') or {}
    out: list[tuple[bytes, bytes]] = []
    for key, value in headers.items():
        values = multi.get(key, [value]) if isinstance(value, str) else list(value)
        for val in values:
            out.append((str(key).lower().encode('latin-1'), str(val).encode('latin-1')))
    return out


def _query_string(event: dict[str, Any]) -> bytes:
    params = event.get('queryStringParameters') or {}
    if params:
        return urlencode(params).encode('ascii')
    return str(event.get('rawQueryString') or '').encode('ascii')


def _path(event: dict[str, Any]) -> str:
    if event.get('path'):
        return str(event['path'])
    return str(event.get('rawPath') or '/')


def _method(event: dict[str, Any]) -> str:
    if event.get('httpMethod'):
        return str(event['httpMethod'])
    return str((event.get('requestContext') or {}).get('http', {}).get('method', 'GET'))


def _server(event: dict[str, Any]) -> tuple[str, int]:
    headers = event.get('headers') or {}
    host = str(headers.get('Host') or headers.get('host') or 'lambda')
    return (host, 443)


def _client(event: dict[str, Any]) -> tuple[str, int]:
    headers = event.get('headers') or {}
    return (str(headers.get('x-forwarded-for') or '127.0.0.1'), 0)


async def _asgi_response(app: Any, event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Translate an API Gateway event to ASGI, run the app, build a response."""
    scope: dict[str, Any] = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': _method(event),
        'scheme': 'https',
        'path': _path(event),
        'raw_path': _path(event).encode('ascii'),
        'query_string': _query_string(event),
        'root_path': '',
        'headers': _headers(event),
        'server': _server(event),
        'client': _client(event),
        'aws.event': event,
        'aws.context': context,
    }

    response: dict[str, Any] = {'status': 500, 'headers': [], 'body': b''}

    async def receive() -> dict[str, Any]:
        return {
            'type': 'http.request',
            'body': _raw_body(event),
            'more_body': False,
        }

    async def send(message: dict[str, Any]) -> None:
        message_type = message.get('type')
        if message_type == 'http.response.start':
            response['status'] = int(message.get('status', 200))
            response['headers'] = [
                (str(k).encode('latin-1'), str(v).encode('latin-1'))
                for k, v in message.get('headers', [])
            ]
        elif message_type == 'http.response.body':
            response['body'] = bytes(response.get('body', b'')) + bytes(message.get('body') or b'')

    await app(scope, receive, send)

    status = int(response.get('status', 200))
    headers: dict[str, str] = {}
    for key, value in response.get('headers', []) or []:
        headers.setdefault(key.decode('latin-1'), value.decode('latin-1'))
    body = response.get('body', b'') or b''

    return {
        'statusCode': status,
        'headers': headers,
        'isBase64Encoded': False,
        'body': body.decode('utf-8', errors='replace'),
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for the FinSight FastAPI application.

    Adapts an API Gateway event to the ASGI application and returns a
    Lambda-compatible response dictionary. The app is built lazily on first
    invocation so cold starts stay small.
    """
    app = _get_app()
    try:
        return asyncio.run(_asgi_response(app, event, context))
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - defensive gateway fallback
        return {
            'statusCode': 502,
            'headers': {'content-type': 'application/json'},
            'body': json.dumps({'message': 'upstream error', 'detail': str(exc)}),
        }


def __getattr__(name: str) -> Any:
    """Resolve ``app`` lazily for ``uvicorn`` and ``from ...main import app``."""
    if name == 'app':
        return _get_app()
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
