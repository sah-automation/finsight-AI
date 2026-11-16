"""Model gateway adapter: thin wrapper around the in-process litellm chain.

This adapter is the *only* place in the gateway entrypoint that calls litellm
directly, satisfying the architectural invariant that external clients live in
adapters/composition. The FastAPI bridge (``finsight.entrypoints.gateway.app``)
is a pure shell that delegates to this adapter.
"""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING, Any

import litellm

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_LOGGER = logging.getLogger(__name__)


async def _resolve_stream(call: Any) -> Any:
    """Call litellm and return the async chunk stream (awaiting coroutines)."""
    result = call()
    if inspect.isawaitable(result):
        result = await result
    return result


class ModelGatewayAdapter:
    """Thin gateway adapter: chat streams NDJSON chunks, embeddings buffered."""

    async def chat_completions(self, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        """Stream litellm chat chunks as litellm-shaped dicts."""
        try:
            stream = await _resolve_stream(lambda: litellm.acompletion(**kwargs))
            first = await stream.__anext__()
        except StopAsyncIteration:
            raise RuntimeError('gateway produced no chunks') from None
        except Exception as exc:
            _LOGGER.warning('gateway chat call failed: %s', exc)
            raise RuntimeError(f'gateway call failed: {exc}') from exc

        yield first
        try:
            async for chunk in stream:
                yield chunk
        except Exception as exc:  # noqa: BLE001 - mid-stream errors surface as an error chunk
            _LOGGER.warning('gateway chat stream failed mid-response: %s', exc)
            yield {'error': {'message': str(exc)}}

    async def embeddings(self, **kwargs: Any) -> dict[str, Any]:
        """Return the litellm-shaped embedding response dict."""
        try:
            result = await _resolve_stream(lambda: litellm.aembedding(**kwargs))
        except Exception as exc:
            _LOGGER.warning('gateway embedding call failed: %s', exc)
            raise RuntimeError(f'gateway call failed: {exc}') from exc
        if isinstance(result, dict):
            return result
        dumped: dict[str, Any] = result.model_dump()
        return dumped


def build_gateway_adapter() -> ModelGatewayAdapter:
    """Factory for composition wiring (issue #330)."""
    return ModelGatewayAdapter()


__all__ = ['ModelGatewayAdapter', 'build_gateway_adapter']
