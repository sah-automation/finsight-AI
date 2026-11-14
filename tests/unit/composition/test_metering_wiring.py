"""Tests that the metering adapter is wired through the composition root."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.adapters.metering.dynamo_metering import DynamoMetering
from finsight.composition import build_container, build_metering
from finsight.composition.adapter_stacks import (
    _build_embedding_stack,
    _build_llm_stack,
    _build_reranker_stack,
)
from finsight.core.config.loader import load_config


def test_build_metering_selects_the_dynamo_adapter() -> None:
    assert isinstance(build_metering(), DynamoMetering)


def test_metering_adapter_uses_the_configured_table_and_prices() -> None:
    config = load_config('test')

    metering = build_metering(config=config)

    assert isinstance(metering, DynamoMetering)
    assert metering.table_name == config.metering.table_name
    assert metering.price_table is not None
    metering.price_table.require_models(
        [
            config.llm.primary_model.model_id,
            config.llm.embedding_model.model_id,
        ]
    )


def test_container_exposes_the_metering_adapter() -> None:
    container = build_container(config=load_config('test'))

    assert isinstance(container.metering, DynamoMetering)
    assert container.meter is container.metering
    assert container.metering_port is container.metering
    assert container['metering'] is container.metering
    assert container.adapters['metering'] is container.metering


def test_injected_metering_adapter_is_preserved() -> None:
    metering = DynamoMetering(table_name='injected-metering')

    container = build_container(config=load_config('test'), metering=metering)

    assert container.metering is metering


# ---------------------------------------------------------------------------
# Metered-identity gate (issue #261): every metered path must record a model
# id that the real price table can price, with a non-None cost.
# ---------------------------------------------------------------------------


async def _ok_llm_completion(**kwargs: Any) -> list[dict[str, Any]]:
    return [{'choices': [{'delta': {'content': 'hello'}}]}]


class _OkEmbedding:
    async def embedding_func(self, **kwargs: Any) -> dict[str, Any]:
        texts = kwargs.get('input') or ['']
        return {'data': [{'embedding': [0.0] * 1024} for _ in texts]}


class _OkScorer:
    async def rerank(self, **kwargs: Any) -> list[dict[str, Any]]:
        documents = kwargs.get('documents') or []
        return [
            {'index': index, 'relevance_score': 1.0 - index * 0.1}
            for index in range(len(documents))
        ]


class _RecordingMetering:
    """Metering port backed by the real adapter so pricing rules apply."""

    def __init__(self) -> None:
        self._adapter = build_metering(config=load_config('test'))
        self.records: list[Any] = []

    @property
    def price_table(self) -> Any:
        return self._adapter.price_table

    async def record_usage(self, *args: Any, **kwargs: Any) -> Any:
        record = await self._adapter.record_usage(*args, **kwargs)
        self.records.append(record)
        return record


def test_metered_stacks_record_priced_model_identities() -> None:
    config = load_config('test')
    metering = _RecordingMetering()

    llm = _build_llm_stack(config=config, metering=metering, completion_func=_ok_llm_completion)
    embedding = _build_embedding_stack(
        config=config, metering=metering, embedding_func=_OkEmbedding().embedding_func
    )
    reranker = _build_reranker_stack(config=config, metering=metering, client=_OkScorer())

    asyncio.run(llm.complete('company-a', prompt='question'))
    asyncio.run(embedding.embed('company-a', ['documentation']))
    asyncio.run(
        reranker.rerank(
            'company-a',
            'question',
            [{'company_id': 'company-a', 'text': f'doc {index}'} for index in range(3)],
        )
    )

    assert metering.records, 'metered stacks must record usage rows'
    by_service: dict[str, list[Any]] = {}
    for record in metering.records:
        by_service.setdefault(str(record.service), []).append(record)
    assert set(by_service) == {'llm', 'embedding', 'rerank'}
    expected_models = {
        'llm': config.llm.primary_model.model_id,
        'embedding': config.llm.embedding_model.model_id,
        'rerank': config.models.rerank.primary,
    }
    for service, model_id in expected_models.items():
        rows = by_service[service]
        assert rows, f'metered {service} path must record at least one usage row'
        for record in rows:  # every recorded row, not just the first per service
            assert record.model == model_id, (
                f'{service} rows must record the priced id {model_id!r}'
            )
            assert record.cost is not None, f'{service} rows must have a priced cost'
            metering.price_table.cost_for(str(record.model), record.units or 1)
