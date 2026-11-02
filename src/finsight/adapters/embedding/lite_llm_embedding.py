# ruff: noqa: BLE001
"""LiteLLM-backed embedding adapter with retries and dimension validation."""

from __future__ import annotations

import logging
from typing import Any

from finsight.domain.ports.embedding_provider import EmbeddingProvider as EmbeddingProviderPort

from ._embedding_embed import (
    _embed,
    _embed_batch_alias,
    _embed_many,
    _embed_text,
    _embed_texts,
)
from ._embedding_helpers import *  # noqa: F403
from ._embedding_helpers import _as_texts, _extract_vectors, _first, _resolve_config  # noqa: F401
from ._embedding_operations import (
    _init_embedding,
)

_LOGGER = logging.getLogger(__name__)

_litellm_module: Any
try:
    import litellm as _litellm_module
except Exception:  # pragma: no cover
    _litellm_module = None

_ORIGINAL_AEMBEDDING = (
    getattr(_litellm_module, 'aembedding', None) if _litellm_module is not None else None
)
aembedding = _ORIGINAL_AEMBEDDING
litellm_aembedding = _ORIGINAL_AEMBEDDING
embedding = getattr(_litellm_module, 'embedding', None) if _litellm_module is not None else None


def _resolve_aembedding() -> Any:
    litellm_fn = None
    if _litellm_module is not None:
        litellm_fn = getattr(_litellm_module, 'aembedding', None)
    module_fn = aembedding
    if module_fn is not None and module_fn is not _ORIGINAL_AEMBEDDING:
        return module_fn
    if litellm_fn is not None:
        return litellm_fn
    if module_fn is not None:
        return module_fn
    sync_fn = getattr(_litellm_module, 'embedding', None) if _litellm_module is not None else None
    if sync_fn is not None:

        async def _wrapped(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[no-untyped-def]
            return sync_fn(*args, **kwargs)

        return _wrapped
    raise RuntimeError('litellm aembedding is unavailable')


# Note: _resolve_aembedding in operations module delegates here.


class LiteLLMEmbedding(EmbeddingProviderPort):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _init_embedding(self, *args, **kwargs)

    async def embed(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await _embed(self, company_id, *args, **kwargs)

    async def embed_texts(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await _embed_texts(self, company_id, *args, **kwargs)

    async def embed_text(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await _embed_text(self, company_id, *args, **kwargs)

    async def embed_batch(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await _embed_batch_alias(self, company_id, *args, **kwargs)

    async def embed_many(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return await _embed_many(self, company_id, *args, **kwargs)


# Override dummy
EmbeddingProvider = LiteLLMEmbedding
Embeddings = LiteLLMEmbedding
LiteLLMEmbeddings = LiteLLMEmbedding
EmbeddingAdapter = LiteLLMEmbedding
EmbeddingGatewayImpl = LiteLLMEmbedding

__all__ = [
    'EmbeddingAdapter',
    'EmbeddingGatewayImpl',
    'EmbeddingProvider',
    'Embeddings',
    'LiteLLMEmbedding',
    'LiteLLMEmbeddings',
]
