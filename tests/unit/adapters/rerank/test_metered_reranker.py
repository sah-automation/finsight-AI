"""Tests that the metered rerank decorator records a priced, qualified model id."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from finsight.adapters.rerank.cohere_reranker import CohereReranker
from finsight.adapters.rerank.metered_reranker import MeteredReranker
from finsight.adapters.rerank.retrying_reranker import RetryingReranker
from finsight.core.config.price_table import load_price_table

QUALIFIED_MODEL = 'cohere/rerank-english-v3.0'  # priced in config/prices.yaml


class RecordingMetering:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record_usage(self, *args: Any, **kwargs: Any) -> None:
        self.records.append({'args': args, 'kwargs': kwargs})


class _OkScorer:
    async def rerank(self, **kwargs: Any) -> list[dict[str, Any]]:
        documents = kwargs.get('documents') or []
        return [
            {'index': index, 'relevance_score': 1.0 - index * 0.1}
            for index in range(len(documents))
        ]


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        provider='cohere',
        model='rerank-english-v3.0',
        top_n=5,
        timeout_seconds=5,
        max_retries=0,
        batch_size=10,
    )


def test_reranker_exposes_qualified_metering_identity() -> None:
    provider = CohereReranker(config=_config(), client=_OkScorer())

    # The provider-facing wire name keeps its stripped prefix ...
    assert provider.model == 'rerank-english-v3.0'
    # ... but the metering identity is the provider-qualified, priced id.
    assert provider.model_id == QUALIFIED_MODEL
    load_price_table().cost_for(provider.model_id, 1)


def test_metered_rerank_records_the_qualified_model_id() -> None:
    metering = RecordingMetering()
    provider = CohereReranker(config=_config(), client=_OkScorer())
    metered = MeteredReranker(RetryingReranker(provider), metering=metering)

    asyncio.run(
        metered.rerank(
            'company-a',
            'question',
            [{'company_id': 'company-a', 'text': f'doc {index}'} for index in range(3)],
        )
    )

    assert metering.records, 'MeteredReranker must record usage around rerank()'
    record = metering.records[0]
    assert record['kwargs'].get('service') == 'rerank'
    assert record['kwargs'].get('model') == QUALIFIED_MODEL
    load_price_table().cost_for(str(record['kwargs'].get('model')), 1)
