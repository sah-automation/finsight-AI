"""Tests that the metered LLM decorator records the gateway's real model id."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway
from finsight.adapters.llm.metered_llm import MeteredLLM
from finsight.adapters.llm.retrying_llm import RetryingLLM
from finsight.core.config.price_table import load_price_table

MODEL_ID = 'gemini-3.8-flash'  # priced in config/prices.yaml


class RecordingMetering:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record_usage(self, *args: Any, **kwargs: Any) -> None:
        self.records.append({'args': args, 'kwargs': kwargs})


async def _ok_completion(**kwargs: Any) -> list[dict[str, Any]]:
    return [{'choices': [{'delta': {'content': 'hello'}}]}]


def test_retrying_llm_exposes_the_gateway_model_id() -> None:
    provider = LiteLLMGateway(completion_func=_ok_completion, model=MODEL_ID, max_retries=0)
    retry = RetryingLLM(provider, retries=1)

    assert retry.model_id == MODEL_ID


def test_metered_llm_records_the_real_model_not_the_llm_fallback() -> None:
    metering = RecordingMetering()
    provider = LiteLLMGateway(completion_func=_ok_completion, model=MODEL_ID, max_retries=0)
    metered = MeteredLLM(RetryingLLM(provider, retries=1), metering=metering)

    asyncio.run(metered.complete('company-a', prompt='question'))

    assert metering.records, 'MeteredLLM must record usage around complete()'
    model = metering.records[0]['kwargs'].get('model')
    assert model == MODEL_ID
    # The recorded identity must be priced (issue #261).
    load_price_table().cost_for(str(model), 1)
