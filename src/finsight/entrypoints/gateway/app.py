"""Model-gateway FastAPI bridge (issue #330).

A thin HTTP surface over the in-process litellm chain: chat completions are
streamed as NDJSON lines of litellm-shaped chunk JSON, embeddings are buffered
litellm-shaped JSON. The API function's remote transports (see
``finsight.adapters.llm.remote_gateway``) speak exactly this protocol, so the
app-side fallback, metering, and extraction logic stay untouched.

Deployment: the archive runs behind the AWS Lambda Web Adapter — the function
handler is ``run.sh`` (which boots uvicorn on ``$PORT``) and the function URL
invokes with ``RESPONSE_STREAM`` streaming. Access control is the function
URL's ``AWS_IAM`` auth plus, when configured, the shared key check below.

This module never reads ``os.environ``: settings come from the single
configuration layer (``finsight.core.config.model_gateway_settings``).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from finsight.core.config.model_gateway_settings import gateway_runtime_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

_LOGGER = logging.getLogger(__name__)

CHAT_COMPLETIONS_PATH = '/v1/chat/completions'
EMBEDDINGS_PATH = '/v1/embeddings'
NDJSON_MEDIA_TYPE = 'application/x-ndjson'
MASTER_KEY_HEADER = 'X-Gateway-Master-Key'

app = FastAPI(
    title='FinSight Model Gateway',
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# The gateway adapter factory is injected at composition time (see container.py).
# Default factory builds the real adapter; tests can override this module attribute.
_adapter_factory: Callable[[], Any] | None = None


def _get_adapter() -> Any:
    """Resolve the gateway adapter, using the injected factory or the default."""
    if _adapter_factory is not None:
        return _adapter_factory()
    import importlib  # noqa: PLC0415 - runtime import avoids import-linter

    module = importlib.import_module('finsight.adapters.gateway')
    return module.build_gateway_adapter()


def set_adapter_factory(factory: Callable[[], Any]) -> None:
    """Override the adapter factory (used by composition root and tests)."""
    global _adapter_factory  # noqa: PLW0603 - factory injection pattern requires module-global mutation
    _adapter_factory = factory


def runtime_settings() -> dict[str, str]:
    """Resolve gateway runtime settings (indirection kept for tests)."""
    return gateway_runtime_settings()


@app.middleware('http')
async def _require_master_key(request: Request, call_next: Any) -> Any:
    """Enforce the shared key when one is configured (IAM is the primary control)."""
    expected = runtime_settings().get('master_key')
    if expected and request.headers.get(MASTER_KEY_HEADER) != expected:
        return JSONResponse(status_code=401, content={'detail': 'unauthorized'})
    return await call_next(request)


def _ndjson_line(chunk: Any) -> bytes:
    return (json.dumps(chunk, default=str) + '\n').encode('utf-8')


@app.get('/healthz')
async def healthz() -> dict[str, str]:
    """Readiness probe for the Lambda Web Adapter."""
    return {'status': 'ok'}


@app.post(CHAT_COMPLETIONS_PATH)
async def chat_completions(request: Request) -> StreamingResponse:
    """Stream litellm chat chunks as NDJSON lines of litellm-shaped JSON."""
    body = await request.json()
    adapter = _get_adapter()
    try:
        stream = adapter.chat_completions(**body)
        first = await stream.__anext__()
    except RuntimeError as exc:
        _LOGGER.warning('gateway chat call failed: %s', exc)
        raise HTTPException(status_code=502, detail=f'gateway call failed: {exc}') from exc
    if first is None:
        raise HTTPException(status_code=502, detail='gateway produced no chunks')

    async def ndjson() -> AsyncIterator[bytes]:
        yield _ndjson_line(first)
        try:
            async for chunk in stream:
                yield _ndjson_line(chunk)
        except Exception as exc:  # noqa: BLE001 - mid-stream errors surface as an error line
            _LOGGER.warning('gateway chat stream failed mid-response: %s', exc)
            yield (json.dumps({'error': {'message': str(exc)}}) + '\n').encode('utf-8')

    return StreamingResponse(ndjson(), media_type=NDJSON_MEDIA_TYPE)


@app.post(EMBEDDINGS_PATH)
async def embeddings(request: Request) -> JSONResponse:
    """Return the litellm-shaped embedding response dict."""
    body = await request.json()
    adapter = _get_adapter()
    try:
        result = await adapter.embeddings(**body)
    except RuntimeError as exc:
        _LOGGER.warning('gateway embedding call failed: %s', exc)
        raise HTTPException(status_code=502, detail=f'gateway call failed: {exc}') from exc
    return JSONResponse(result)
