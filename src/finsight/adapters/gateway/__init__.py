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

import boto3  # type: ignore[import-untyped]
import litellm

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_LOGGER = logging.getLogger(__name__)

_MASTER_KEY_CACHE: str | None = None


async def _resolve_stream(call: Any) -> Any:
    """Call litellm and return the async chunk stream (awaiting coroutines)."""
    result = call()
    if inspect.isawaitable(result):
        result = await result
    return result


class ModelGatewayAdapter:
    """Thin gateway adapter: chat streams NDJSON chunks, embeddings buffered."""

    def __init__(self, master_key_param: str | None = None, region: str | None = None) -> None:
        """Initialize the adapter.

        Args:
            master_key_param: SSM parameter name for the master key.
            region: AWS region for SSM client. Defaults to us-east-1.
        """
        self._master_key_param = master_key_param
        self._region = region or 'us-east-1'

    async def _fetch_master_key(self) -> str | None:
        """Fetch the master key from SSM parameter store (cached after first call)."""
        global _MASTER_KEY_CACHE  # noqa: PLW0603 - module-level cache for SSM key
        if _MASTER_KEY_CACHE is not None:
            return _MASTER_KEY_CACHE

        param_name = self._master_key_param
        if not param_name:
            return None

        try:
            client = boto3.client('ssm', region_name=self._region)
            response = client.get_parameter(Name=param_name, WithDecryption=True)
            value: str = response['Parameter']['Value']
        except Exception as exc:  # noqa: BLE001 - fail open, log and continue
            _LOGGER.warning('Failed to fetch master key from SSM (%s): %s', param_name, exc)
            return None
        else:
            _MASTER_KEY_CACHE = value
            return value

    def _get_master_key(self) -> str | None:
        """Get the master key, fetching from SSM if not cached."""
        if _MASTER_KEY_CACHE is not None:
            return _MASTER_KEY_CACHE
        return None  # Will be fetched on first check via runtime_settings

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


def build_gateway_adapter(
    master_key_param: str | None = None, region: str | None = None
) -> ModelGatewayAdapter:
    """Factory for composition wiring (issue #330)."""
    return ModelGatewayAdapter(master_key_param=master_key_param, region=region)


__all__ = ['ModelGatewayAdapter', 'build_gateway_adapter']
