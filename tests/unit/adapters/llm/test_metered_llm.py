"""Tests that the metered LLM decorator records the gateway's real model id."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway
from finsight.adapters.llm.metered_llm import MeteredLLM
from finsight.adapters.llm.retrying_llm import RetryingLLM
from finsight.core.config.loader import load_config
from finsight.core.config.price_table import load_price_table


class RecordingMetering:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record_usage(self, *args: Any, **kwargs: Any) -> None:
        self.records.append({'args': args, 'kwargs': kwargs})


async def _ok_completion(**kwargs: Any) -> list[dict[str, Any]]:
    return [{'choices': [{'delta': {'content': 'hello'}}]}]


async def _usage_completion(**kwargs: Any) -> list[dict[str, Any]]:
    return [
        {
            'choices': [{'delta': {'content': 'hello'}}],
            'usage': {'prompt_tokens': 12, 'completion_tokens': 8, 'total_tokens': 20},
        }
    ]


def test_retrying_llm_exposes_the_gateway_model_id() -> None:
    config = load_config('test')
    model_id = config.llm.primary_model.model_id
    provider = LiteLLMGateway(completion_func=_ok_completion, model=model_id, max_retries=0)
    retry = RetryingLLM(provider, retries=1)

    assert retry.model_id == model_id
    # The recorded identity must be priced (issue #261).
    load_price_table().cost_for(retry.model_id, 1)


def test_metered_llm_records_the_real_model_not_the_llm_fallback() -> None:
    config = load_config('test')
    model_id = config.llm.primary_model.model_id
    metering = RecordingMetering()
    provider = LiteLLMGateway(completion_func=_ok_completion, model=model_id, max_retries=0)
    metered = MeteredLLM(RetryingLLM(provider, retries=1), metering=metering)

    asyncio.run(metered.complete('company-a', prompt='question'))

    assert metering.records, 'MeteredLLM must record usage around complete()'
    model = metering.records[0]['kwargs'].get('model')
    assert model == model_id
    load_price_table().cost_for(str(model), 1)


def test_metered_llm_records_token_units_and_priced_model() -> None:
    config = load_config('test')
    model_id = config.llm.primary_model.model_id
    metering = RecordingMetering()
    provider = LiteLLMGateway(completion_func=_usage_completion, model=model_id, max_retries=0)
    metered = MeteredLLM(RetryingLLM(provider, retries=0), metering=metering)

    asyncio.run(metered.complete('company-a', prompt='question'))

    assert metering.records, 'MeteredLLM must record usage around complete()'
    kwargs = metering.records[0]['kwargs']
    assert kwargs.get('model') == model_id
    # Token units come from the real usage chunk, not the placeholder unit.
    assert kwargs.get('units') == 20
    # The priced model identity must resolve a cost.
    load_price_table().cost_for(str(model_id), int(kwargs.get('units') or 1))


def test_metered_llm_unpriced_model_still_writes_row_exposing_gap() -> None:
    # A paid call to an unpriced model identity must still write a usage row and
    # expose the pricing gap rather than silently recording zero cost.
    metering = RecordingMetering()
    provider = LiteLLMGateway(
        completion_func=_usage_completion, model='provider/unpriced-model', max_retries=0
    )
    metered = MeteredLLM(RetryingLLM(provider, retries=0), metering=metering)

    asyncio.run(metered.complete('company-a', prompt='question'))

    assert metering.records, 'MeteredLLM must still record usage for an unpriced model'
    kwargs = metering.records[0]['kwargs']
    assert kwargs.get('model') == 'provider/unpriced-model'
    assert kwargs.get('units') == 20
    # No price is configured: cost must be absent (gap exposed), never zero.
    assert kwargs.get('estimated_cost') is None
    assert kwargs.get('cost') is None
