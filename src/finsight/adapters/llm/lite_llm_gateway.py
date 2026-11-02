# ruff: noqa: BLE001, ARG004
# mypy: disable-error-code="misc,method-assign,no-untyped-def,arg-type,attr-defined"
"""LiteLLM-backed model gateway with failover, backup requests, and metering."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from finsight.domain.ports.llm_gateway import LLMGateway as LLMGatewayPort

from ._llm_gateway_init import _init_llm_gateway
from ._llm_gateway_public import _complete, _stream
from ._llm_gateway_stream import _attempt_step, _open_stream, _stream_chain, _to_chunk
from ._llm_gateway_usage import (
    _alert_fallback_3,
    _choose_chain,
    _extract_company_id,
    _invoke_metering,
    _record_usage,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)

_litellm_module: Any
try:
    import litellm as _litellm_module
except Exception:  # pragma: no cover
    _litellm_module = None

_ORIGINAL_ACOMPLETION = (
    getattr(_litellm_module, 'acompletion', None) if _litellm_module is not None else None
)
acompletion = _ORIGINAL_ACOMPLETION
litellm_acompletion = _ORIGINAL_ACOMPLETION


class _GatewayStreamChunk(str):
    def __init__(self, text: str, **metadata: Any) -> None:
        super().__init__()
        self._text = text
        self._metadata = dict(metadata)
        self._metadata.setdefault('content', text)
        self._metadata.setdefault('text', text)
        self._metadata.setdefault('delta', text)
        self._metadata.setdefault('type', 'delta')

    def __new__(cls, text: str, **metadata: Any) -> _GatewayStreamChunk:
        return super().__new__(cls, text)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            return self._metadata.get(key)
        return super().__getitem__(key)

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        if name in self._metadata:
            return self._metadata[name]
        raise AttributeError(name)

    def get(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(key, default)

    @property
    def content(self) -> str:
        return str(self._metadata.get('content', self._text))

    @property
    def text(self) -> str:
        return self._text


def _resolve_acompletion() -> Callable[..., Any]:
    litellm_fn = None
    if _litellm_module is not None:
        litellm_fn = getattr(_litellm_module, 'acompletion', None)
    module_fn = acompletion
    if module_fn is not None and module_fn is not _ORIGINAL_ACOMPLETION:
        return cast('Callable[..., Any]', module_fn)
    if litellm_fn is not None:
        return cast('Callable[..., Any]', litellm_fn)
    if module_fn is not None:
        return cast('Callable[..., Any]', module_fn)
    completion_fn = getattr(_litellm_module, 'completion', None) if _litellm_module else None
    if completion_fn is not None:

        async def _wrapped(self, *args: Any, **kwargs: Any) -> Any:
            return completion_fn(*args, **kwargs)

        return _wrapped
    raise RuntimeError('litellm acompletion is unavailable')


class LiteLLMGateway(LLMGatewayPort):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _init_llm_gateway(self, *args, **kwargs)

    # internal method bindings
    _choose_chain = _choose_chain
    _extract_company_id = _extract_company_id
    _record_usage = _record_usage
    _invoke_metering = _invoke_metering
    _alert_fallback_3 = _alert_fallback_3
    _open_stream = _open_stream
    _attempt_step = _attempt_step
    _stream_chain_helper = staticmethod(_stream_chain)

    async def stream(self, company_id: object = None, *args: Any, **kwargs: Any) -> Any:

        async def gen() -> Any:
            async for item in _stream(self, company_id, args, kwargs, _GatewayStreamChunk):
                yield item

        return gen()

    async def complete(self, company_id: object = None, *args: Any, **kwargs: Any) -> Any:
        return await _complete(self, company_id, args, kwargs, _GatewayStreamChunk)

    async def generate(self, company_id: object = None, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    async def chat(self, company_id: object = None, *args: Any, **kwargs: Any) -> Any:
        return await self.complete(company_id, *args, **kwargs)

    async def generate_text(self, company_id: object = None, *args: Any, **kwargs: Any) -> object:
        return await self.complete(company_id, *args, **kwargs)

    async def stream_complete(self, company_id: object = None, *args: Any, **kwargs: Any) -> object:
        return self.stream(company_id, *args, **kwargs)

    async def stream_text(self, company_id: object = None, *args: Any, **kwargs: Any) -> object:
        return self.stream(company_id, *args, **kwargs)

    @staticmethod
    def _to_chunk(chunk: Any, model_id: str) -> Any:
        return _to_chunk(chunk, model_id, _GatewayStreamChunk)


# Async public method implementations (kept as module functions for thin class).


async def _complete_method(self: Any, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
    return await _complete(self, company_id, args, kwargs, _GatewayStreamChunk)


async def _stream_method(self: Any, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
    async for item in _stream(self, company_id, args, kwargs, _GatewayStreamChunk):
        yield item


async def _generate_method(self: Any, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
    return await _complete_method(self, company_id, *args, **kwargs)


LiteLLMGateway.stream = _stream_method
LiteLLMGateway.complete = _complete_method
LiteLLMGateway.generate = _generate_method
LiteLLMGateway.chat = _generate_method
LiteLLMGateway.generate_text = _generate_method
LiteLLMGateway.stream_complete = _stream_method
LiteLLMGateway.stream_text = _stream_method


# Alias loops expected by tests


LLMGateway = LiteLLMGateway
LiteLLM = LiteLLMGateway
ModelGateway = LiteLLMGateway
LLMAdapter = LiteLLMGateway
Gateway = LiteLLMGateway

GatewayStreamChunk = _GatewayStreamChunk

__all__ = [
    'Gateway',
    'GatewayStreamChunk',
    'LLMAdapter',
    'LLMGateway',
    'LiteLLM',
    'LiteLLMGateway',
    'ModelGateway',
    '_GatewayStreamChunk',
]
