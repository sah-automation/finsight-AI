"""Tests that the metered rerank decorator records a priced, qualified model id."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.adapters.rerank.cohere_reranker import CohereReranker
from finsight.adapters.rerank.metered_reranker import MeteredReranker
from finsight.adapters.rerank.retrying_reranker import RetryingReranker
from finsight.core.config.loader import load_config
from finsight.core.config.price_table import load_price_table


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


def test_reranker_exposes_qualified_metering_identity() -> None:
    config = load_config('test')
    provider = CohereReranker(config=config, client=_OkScorer())

    # The provider-facing wire name keeps its prefix-stripped form ...
    assert provider.model == config.reranker.model
    # ... but the metering identity is the provider-qualified, priced id.
    assert provider.model_id == config.models.rerank.primary
    load_price_table().cost_for(provider.model_id, 1)


def test_metered_rerank_records_the_qualified_model_id() -> None:
    config = load_config('test')
    metering = RecordingMetering()
    provider = CohereReranker(config=config, client=_OkScorer())
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
    assert record['kwargs'].get('model') == config.models.rerank.primary
    load_price_table().cost_for(str(record['kwargs'].get('model')), 1)
