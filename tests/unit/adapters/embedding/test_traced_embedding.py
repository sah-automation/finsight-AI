"""Unit tests for TracedEmbedding using fake embedding functions (no real model calls)."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import pytest

from finsight.adapters.embedding.lite_llm_embedding import LiteLLMEmbedding
from finsight.adapters.embedding.metered_embedding import MeteredEmbedding
from finsight.adapters.embedding.retrying_embedding import RetryingEmbedding
from finsight.adapters.embedding.traced_embedding import TracedEmbedding
from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.adapters.tracing.tracing_adapter import TracingAdapter

pytestmark = pytest.mark.unit

COMPANY = 'company-a'


async def _ok_embedding(**kwargs: Any) -> dict[str, Any]:
    await asyncio.sleep(0.01)
    return {'data': [{'embedding': [0.1, 0.2]}]}


def _make_stack(tracing: Any) -> TracedEmbedding:
    provider = LiteLLMEmbedding(embedding_func=_ok_embedding, model_id='test-model', dimensions=2)
    return TracedEmbedding(
        MeteredEmbedding(RetryingEmbedding(provider), metering=None), tracing=tracing
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
def test_traced_embedding_span_emitted_after_inner_call(tracer_factory: Any) -> None:
    tracer = tracer_factory()
    traced = _make_stack(tracer)

    result = asyncio.run(traced.embed(COMPANY, text='hello'))

    assert result == [0.1, 0.2]
    attrs = _span_attrs(tracer)
    assert isinstance(attrs.get('duration_ms'), (int, float))
    assert attrs['duration_ms'] > 0
    assert isinstance(attrs.get('retry_count'), int)
    assert isinstance(attrs.get('cache_hit'), bool)
    assert isinstance(attrs.get('fallback_tags'), list)


def test_traced_embedding_without_tracer_still_completes() -> None:
    traced = _make_stack(None)
    result = asyncio.run(traced.embed(COMPANY, text='hello'))
    assert result == [0.1, 0.2]
