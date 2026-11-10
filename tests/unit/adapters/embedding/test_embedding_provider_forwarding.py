"""Behavioral tests: embedding adapter forwards AI Studio route and dimensions."""

from __future__ import annotations

import asyncio

import pytest

from finsight.adapters.embedding.lite_llm_embedding import LiteLLMEmbedding


def test_embed_batch_forwards_ai_studio_route_and_dimensions() -> None:
    """Adapter forwards the AI Studio route and configured dimensions."""
    captured: dict = {}

    async def provider_func(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)  # type: ignore[arg-type]
        dims = kwargs.get('dimensions', 1024)
        return {'data': [{'embedding': [0.0] * int(dims)}]}

    provider = LiteLLMEmbedding(
        embedding_func=provider_func,
        model_id='gemini/gemini-embedding-001',
        dimensions=1024,
    )

    asyncio.run(provider.embed('company-a', texts=['ping']))

    assert captured['model'] == 'gemini/gemini-embedding-001'
    assert captured['dimensions'] == 1024
    assert captured['input'] == ['ping']


def test_mismatched_returned_dimension_still_raises() -> None:
    """A mismatched returned dimension still raises ValueError."""

    async def provider_func(**kwargs: object) -> dict[str, object]:
        return {'data': [{'embedding': [0.0] * 512}]}

    provider = LiteLLMEmbedding(
        embedding_func=provider_func,
        model_id='gemini/gemini-embedding-001',
        dimensions=1024,
    )

    with pytest.raises(ValueError, match='dimensions'):
        asyncio.run(provider.embed('company-a', text='ping'))
