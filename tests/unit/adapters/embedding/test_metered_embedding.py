"""Regression lock: the metered embedding decorator records the real model id."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.adapters.embedding.lite_llm_embedding import LiteLLMEmbedding
from finsight.adapters.embedding.metered_embedding import MeteredEmbedding
from finsight.adapters.embedding.retrying_embedding import RetryingEmbedding
from finsight.core.config.price_table import load_price_table

MODEL_ID = 'gemini-embedding-001'  # priced in config/prices.yaml


class RecordingMetering:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record_usage(self, *args: Any, **kwargs: Any) -> None:
        self.records.append({'args': args, 'kwargs': kwargs})


async def _ok_embedding_func(**kwargs: Any) -> dict[str, Any]:
    texts = kwargs.get('input') or ['']
    return {'data': [{'embedding': [0.0] * 1024} for _ in texts]}


def test_metered_embedding_delegates_model_identity_through_the_retry_decorator() -> None:
    metering = RecordingMetering()
    provider = LiteLLMEmbedding(embedding_func=_ok_embedding_func, model_id=MODEL_ID)
    metered = MeteredEmbedding(RetryingEmbedding(provider), metering=metering)

    asyncio.run(metered.embed('company-a', ['sample text']))

    assert metering.records, 'MeteredEmbedding must record usage around embed()'
    model = metering.records[0]['kwargs'].get('model')
    assert model == MODEL_ID
    load_price_table().cost_for(str(model), 1)
