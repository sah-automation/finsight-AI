"""Unit tests for TracedLLM using fake completion functions (no real model calls)."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import pytest

from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway
from finsight.adapters.llm.metered_llm import MeteredLLM
from finsight.adapters.llm.retrying_llm import RetryingLLM
from finsight.adapters.llm.traced_llm import TracedLLM
from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.adapters.tracing.tracing_adapter import TracingAdapter

pytestmark = pytest.mark.unit

COMPANY = 'company-a'


async def _ok_completion(**kwargs: Any) -> list[dict[str, Any]]:
    await asyncio.sleep(0.01)
    return [{'choices': [{'delta': {'content': 'hello'}}]}]


def _make_stack(tracing: Any) -> TracedLLM:
    provider = LiteLLMGateway(completion_func=_ok_completion, model='test-model', max_retries=0)
    return TracedLLM(MeteredLLM(RetryingLLM(provider, retries=0), metering=None), tracing=tracing)


def _span_attrs(tracer: Any, company: Any = COMPANY) -> dict[str, Any]:
    spans = tracer.emitted_spans(company)  # type: ignore[attr-defined]
    assert len(spans) == 1
    return spans[0].attributes


@pytest.mark.parametrize(
    'tracer_factory',
    [
        partial(TracingAdapter, service_name='test', enabled=True),
        DisabledTracer,
    ],
)
def test_traced_llm_complete_emits_span_with_real_duration(tracer_factory: Any) -> None:
    tracer = tracer_factory()
    traced = _make_stack(tracer)

    result = asyncio.run(traced.complete(COMPANY, prompt='question'))

    assert 'hello' in str(result)
    attrs = _span_attrs(tracer)
    assert isinstance(attrs.get('duration_ms'), (int, float))
    assert attrs['duration_ms'] > 0
    assert isinstance(attrs.get('retry_count'), int)
    assert isinstance(attrs.get('cache_hit'), bool)


@pytest.mark.parametrize(
    'tracer_factory',
    [
        partial(TracingAdapter, service_name='test', enabled=True),
        DisabledTracer,
    ],
)
def test_traced_llm_stream_emits_one_span_with_first_token_latency(
    tracer_factory: Any,
) -> None:
    tracer = tracer_factory()
    traced = _make_stack(tracer)

    async def _consume() -> list[Any]:
        return [chunk async for chunk in traced.stream(COMPANY, prompt='question')]

    chunks = asyncio.run(_consume())

    assert chunks
    attrs = _span_attrs(tracer)
    assert isinstance(attrs.get('first_token_latency_ms'), (int, float))
    assert attrs['first_token_latency_ms'] > 0
    assert attrs.get('duration_ms', 0) > 0


def test_traced_llm_without_tracer_still_completes() -> None:
    traced = _make_stack(None)
    result = asyncio.run(traced.complete(COMPANY, prompt='question'))
    assert 'hello' in str(result)


async def _usage_completion(**kwargs: Any) -> list[dict[str, Any]]:
    await asyncio.sleep(0.01)
    return [
        {
            'choices': [{'delta': {'content': 'hello'}}],
            'usage': {'prompt_tokens': 12, 'completion_tokens': 8, 'total_tokens': 20},
        }
    ]


async def _usage_stream(**kwargs: Any) -> list[dict[str, Any]]:
    # The final chunk carries usage only (no text) and must not surface as answer content.
    await asyncio.sleep(0.01)
    return [
        {'choices': [{'delta': {'content': 'hel'}}]},
        {'choices': [{'delta': {'content': 'lo'}}]},
        {'choices': [], 'usage': {'prompt_tokens': 12, 'completion_tokens': 8, 'total_tokens': 20}},
    ]


def _make_stack_with_usage(tracing: Any, completion_func: Any) -> TracedLLM:
    provider = LiteLLMGateway(completion_func=completion_func, model='test-model', max_retries=0)
    return TracedLLM(MeteredLLM(RetryingLLM(provider, retries=0), metering=None), tracing=tracing)


def test_traced_llm_complete_span_carries_token_counts() -> None:
    tracer = TracingAdapter(service_name='test', enabled=True)
    traced = _make_stack_with_usage(tracer, _usage_completion)

    result = asyncio.run(traced.complete(COMPANY, prompt='question'))

    assert 'hello' in str(result)
    attrs = tracer.emitted_spans(COMPANY)[0].attributes
    assert attrs.get('tokens_prompt') == 12
    assert attrs.get('tokens_completion') == 8
    assert attrs.get('tokens_total') == 20


def test_traced_llm_stream_usage_chunk_not_emitted_as_content() -> None:
    tracer = TracingAdapter(service_name='test', enabled=True)
    traced = _make_stack_with_usage(tracer, _usage_stream)

    async def _consume() -> list[str]:
        chunks: list[str] = []
        async for chunk in traced.stream(COMPANY, prompt='question'):
            chunks.append(str(chunk))
        return chunks

    chunks = asyncio.run(_consume())

    # Usage-only final chunk must not surface as answer content.
    assert chunks == ['hel', 'lo']
    spans = tracer.emitted_spans(COMPANY)
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs.get('tokens_prompt') == 12
    assert attrs.get('tokens_completion') == 8
    assert attrs.get('tokens_total') == 20
    assert isinstance(attrs.get('first_token_latency_ms'), (int, float))
    assert attrs['first_token_latency_ms'] > 0
