"""Unit tests for TracedReranker using fake scorer functions (no real model calls)."""

from __future__ import annotations

import asyncio
from functools import partial
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.adapters.rerank.cohere_reranker import CohereReranker
from finsight.adapters.rerank.metered_reranker import MeteredReranker
from finsight.adapters.rerank.retrying_reranker import RetryingReranker
from finsight.adapters.rerank.traced_reranker import TracedReranker
from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.adapters.tracing.tracing_adapter import TracingAdapter

pytestmark = pytest.mark.unit

COMPANY = 'company-a'


class _OkScorer:
    async def rerank(self, **kwargs: Any) -> list[dict[str, Any]]:
        await asyncio.sleep(0.01)
        documents = kwargs.get('documents') or []
        return [{'index': index, 'relevance_score': 1.0} for index in range(len(documents))]


class _FailingThenOkScorer:
    """Fails once then succeeds, exercising a real retry."""

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


def _make_stack(tracing: Any, scorer: Any) -> TracedReranker:
    provider = CohereReranker(client=scorer, config=_rerank_config())
    return TracedReranker(
        MeteredReranker(RetryingReranker(provider, retries=1), metering=None), tracing=tracing
    )


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
def test_traced_reranker_span_emitted_after_inner_call(tracer_factory: Any) -> None:
    tracer = tracer_factory()
    traced = _make_stack(tracer, _OkScorer())

    result = asyncio.run(
        traced.rerank(
            COMPANY, question='which?', candidates=[{'company_id': COMPANY, 'text': 'doc'}]
        )
    )

    assert list(result)
    attrs = _span_attrs(tracer)
    assert isinstance(attrs.get('duration_ms'), (int, float))
    assert attrs['duration_ms'] > 0
    assert isinstance(attrs.get('retry_count'), int)
    assert isinstance(attrs.get('cache_hit'), bool)
    assert isinstance(attrs.get('fallback_tags'), list)


@pytest.mark.parametrize(
    'tracer_factory',
    [
        partial(TracingAdapter, service_name='test', enabled=True),
        DisabledTracer,
    ],
)
def test_traced_reranker_retry_count_is_real_when_retries_happen(
    tracer_factory: Any,
) -> None:
    tracer = tracer_factory()
    scorer = _FailingThenOkScorer()
    traced = _make_stack(tracer, scorer)

    result = asyncio.run(
        traced.rerank(
            COMPANY, question='which?', candidates=[{'company_id': COMPANY, 'text': 'doc'}]
        )
    )

    assert list(result)
    assert scorer.attempts == 2  # one failure + one success
    attrs = _span_attrs(tracer)
    assert isinstance(attrs.get('retry_count'), int)
    assert isinstance(attrs.get('retries'), int)


def test_traced_reranker_without_tracer_still_completes() -> None:
    traced = _make_stack(None, _OkScorer())
    result = asyncio.run(
        traced.rerank(
            COMPANY, question='which?', candidates=[{'company_id': COMPANY, 'text': 'doc'}]
        )
    )
    assert list(result)
