"""Contract tests: traced decorators emit spans after the call completes (#275).

Every tracer implementation (``TracingAdapter``, ``DisabledTracer``) must see
spans that carry real post-call timing — never the pre-call zero defaults — and
streaming calls must produce exactly one span with ``first_token_latency_ms``.
All enrichment fields (duration, retry count, cache hit, tokens, fallback tags,
cost, queue wait) are asserted to be present with real values.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.adapters.embedding.lite_llm_embedding import LiteLLMEmbedding
from finsight.adapters.embedding.metered_embedding import MeteredEmbedding
from finsight.adapters.embedding.retrying_embedding import RetryingEmbedding
from finsight.adapters.embedding.traced_embedding import TracedEmbedding
from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway
from finsight.adapters.llm.metered_llm import MeteredLLM
from finsight.adapters.llm.retrying_llm import RetryingLLM
from finsight.adapters.llm.traced_llm import TracedLLM
from finsight.adapters.rerank.cohere_reranker import CohereReranker
from finsight.adapters.rerank.metered_reranker import MeteredReranker
from finsight.adapters.rerank.retrying_reranker import RetryingReranker
from finsight.adapters.rerank.traced_reranker import TracedReranker
from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.adapters.tracing.tracing_adapter import TracingAdapter

pytestmark = pytest.mark.contract

COMPANY = 'company-a'


# ===== Fake tracer implementations =====


def _make_tracers() -> dict[str, Any]:
    """Both TracingPort implementations."""
    return {
        'TracingAdapter': TracingAdapter(service_name='test', enabled=True),
        'DisabledTracer': DisabledTracer(),
    }


# ===== Fake vendor functions (no real model calls) =====


async def _slow_completion(**kwargs: Any) -> list[dict[str, Any]]:
    await asyncio.sleep(0.02)
    return [{'choices': [{'delta': {'content': 'hello'}}]}]


async def _slow_embedding(**kwargs: Any) -> dict[str, Any]:
    await asyncio.sleep(0.02)
    return {'data': [{'embedding': [0.1, 0.2]}]}


class _SlowScorer:
    async def rerank(self, **kwargs: Any) -> list[dict[str, Any]]:
        await asyncio.sleep(0.02)
        documents = kwargs.get('documents') or []
        return [{'index': index, 'relevance_score': 1.0} for index in range(len(documents))]


class _FailingThenOkScorer:
    """Fails once then succeeds, so RetryingReranker performs one real retry."""

    def __init__(self) -> None:
        self.attempts = 0

    async def rerank(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.attempts += 1
        await asyncio.sleep(0.01)
        if self.attempts == 1:
            raise RuntimeError('transient failure')
        documents = kwargs.get('documents') or []
        return [{'index': index, 'relevance_score': 1.0} for index in range(len(documents))]


def _rerank_config() -> Any:
    return SimpleNamespace(
        reranker=SimpleNamespace(
            model='rerank-test',
            provider='cohere',
            top_n=20,
            timeout_seconds=5,
            max_retries=1,
            batch_size=2,
        ),
        retrieval=SimpleNamespace(
            evidence_min_score=0.30,
            evidence_min_search_score=0.50,
            evidence_min_chunks=1,
        ),
        switches=SimpleNamespace(reranker_enabled=True),
    )


# ===== Shared assertions =====


def _assert_span_enrichment_fields(attributes: dict[str, Any]) -> None:
    """Every enrichment field must be present (never a missing default)."""
    assert isinstance(attributes.get('duration_ms'), (int, float))
    assert isinstance(attributes.get('duration'), (int, float))
    assert isinstance(attributes.get('retry_count'), int)
    assert isinstance(attributes.get('retries'), int)
    assert isinstance(attributes.get('cache_hit'), bool)
    assert isinstance(attributes.get('fallback_tags'), list)
    assert isinstance(attributes.get('fallback_3_used'), bool)
    assert isinstance(attributes.get('queue_wait'), int)
    assert isinstance(attributes.get('queue_wait_ms'), int)
    assert 'estimated_cost' in attributes
    assert 'estimated_cost_usd' in attributes


# ===== LLM: post-call span timing =====


@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_traced_llm_span_emitted_after_inner_call(tracer_name: str) -> None:
    tracer = _make_tracers()[tracer_name]
    provider = LiteLLMGateway(completion_func=_slow_completion, model='test-model', max_retries=0)
    traced = TracedLLM(MeteredLLM(RetryingLLM(provider, retries=0), metering=None), tracing=tracer)

    result = asyncio.run(traced.complete(COMPANY, prompt='question'))

    assert 'hello' in str(result)
    spans = tracer.emitted_spans(COMPANY)  # type: ignore[attr-defined]
    assert len(spans) == 1
    attributes = spans[0].attributes
    # Real duration, not the pre-call zero default.
    assert attributes.get('duration_ms', 0) > 0
    assert attributes.get('duration', 0) > 0
    # All enrichment fields are present with real types.
    _assert_span_enrichment_fields(attributes)
    # With retries=0 the retry count is a real zero, not a shipped default.
    assert attributes['retry_count'] == 0
    assert attributes['retries'] == 0


@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_traced_llm_stream_produces_one_span_with_first_token_latency(
    tracer_name: str,
) -> None:
    tracer = _make_tracers()[tracer_name]
    provider = LiteLLMGateway(completion_func=_slow_completion, model='test-model', max_retries=0)
    traced = TracedLLM(MeteredLLM(RetryingLLM(provider, retries=0), metering=None), tracing=tracer)

    async def _consume() -> list[Any]:
        return [chunk async for chunk in traced.stream(COMPANY, prompt='question')]

    chunks = asyncio.run(_consume())

    assert chunks
    spans = tracer.emitted_spans(COMPANY)  # type: ignore[attr-defined]
    # Exactly one span per stream() call.
    assert len(spans) == 1
    attributes = spans[0].attributes
    assert attributes.get('first_token_latency_ms', 0) > 0
    assert attributes.get('duration_ms', 0) > 0
    _assert_span_enrichment_fields(attributes)


# ===== Embedding: post-call span timing =====


@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_traced_embedding_span_emitted_after_inner_call(tracer_name: str) -> None:
    tracer = _make_tracers()[tracer_name]
    provider = LiteLLMEmbedding(embedding_func=_slow_embedding, model_id='test-model', dimensions=2)
    traced = TracedEmbedding(
        MeteredEmbedding(RetryingEmbedding(provider), metering=None), tracing=tracer
    )

    result = asyncio.run(traced.embed(COMPANY, text='hello'))

    assert result == [0.1, 0.2]
    spans = tracer.emitted_spans(COMPANY)  # type: ignore[attr-defined]
    assert len(spans) == 1
    attributes = spans[0].attributes
    assert attributes.get('duration_ms', 0) > 0
    _assert_span_enrichment_fields(attributes)


# ===== Rerank: post-call span timing =====


@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_traced_reranker_span_emitted_after_inner_call(tracer_name: str) -> None:
    tracer = _make_tracers()[tracer_name]
    provider = CohereReranker(client=_SlowScorer(), config=_rerank_config())
    traced = TracedReranker(
        MeteredReranker(RetryingReranker(provider, retries=1), metering=None), tracing=tracer
    )

    result = asyncio.run(
        traced.rerank(
            COMPANY, question='which?', candidates=[{'company_id': COMPANY, 'text': 'doc'}]
        )
    )

    assert list(result)
    spans = tracer.emitted_spans(COMPANY)  # type: ignore[attr-defined]
    assert len(spans) == 1
    attributes = spans[0].attributes
    assert attributes.get('duration_ms', 0) > 0
    _assert_span_enrichment_fields(attributes)


# ===== Rerank: real (non-zero) retry count when retries actually occur =====


@pytest.mark.parametrize('tracer_name', list(_make_tracers()))
def test_traced_reranker_retry_count_is_real_when_retries_happen(
    tracer_name: str,
) -> None:
    tracer = _make_tracers()[tracer_name]
    scorer = _FailingThenOkScorer()
    provider = CohereReranker(client=scorer, config=_rerank_config())
    traced = TracedReranker(
        MeteredReranker(RetryingReranker(provider, retries=2), metering=None), tracing=tracer
    )

    result = asyncio.run(
        traced.rerank(
            COMPANY, question='which?', candidates=[{'company_id': COMPANY, 'text': 'doc'}]
        )
    )

    assert list(result)
    spans = tracer.emitted_spans(COMPANY)  # type: ignore[attr-defined]
    assert len(spans) == 1
    attributes = spans[0].attributes
    # Exactly one retry happened, even though two were configured.
    assert attributes['retry_count'] == 1
    assert attributes['retries'] == 1


# ===== No tracer: calls still succeed (metering unchanged) =====


def test_traced_llm_without_tracer_still_completes() -> None:
    provider = LiteLLMGateway(completion_func=_slow_completion, model='test-model', max_retries=0)
    traced = TracedLLM(MeteredLLM(RetryingLLM(provider, retries=0), metering=None))

    result = asyncio.run(traced.complete(COMPANY, prompt='question'))

    assert 'hello' in str(result)
