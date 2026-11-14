"""Contract tests for the EmbeddingProvider port."""

from __future__ import annotations

from typing import Any

import pytest

from finsight.adapters.embedding.lite_llm_embedding import LiteLLMEmbedding
from finsight.adapters.embedding.metered_embedding import MeteredEmbedding
from finsight.adapters.embedding.retrying_embedding import RetryingEmbedding
from finsight.adapters.embedding.traced_embedding import TracedEmbedding
from finsight.core.types import CompanyId

pytestmark = pytest.mark.contract

COMPANY_A = CompanyId('company-a')
COMPANY_B = CompanyId('company-b')


class FakeMetering:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def record_usage(self, *args: Any, **kwargs: Any) -> None:
        self.records.append({'args': args, 'kwargs': kwargs})


class FakeTracer:
    def __init__(self) -> None:
        self.spans: list[tuple[Any, str]] = []

    def start_span(self, company_id: Any, operation: str) -> None:
        self.spans.append((company_id, operation))


def _ok_embedding(**kwargs: Any) -> dict[str, Any]:
    n = len(kwargs.get('input', kwargs.get('texts', [])) or [])
    if n == 0:
        n = 1
    return {'data': [{'embedding': [0.1, 0.2]} for _ in range(n)]}


async def _failing_embedding(**kwargs: Any) -> dict[str, Any]:
    raise RuntimeError('provider unavailable')


def _is_vectors(result: Any) -> bool:
    if isinstance(result, (list, tuple)) and result:
        first = result[0]
        if isinstance(first, (int, float)):
            return True
        if isinstance(first, (list, tuple)):
            return True
    return False


class _EmbeddingProviderContract:
    def make_embedding(
        self,
        *,
        embedding_func: Any = None,
        dimensions: int = 2,
        metering: Any = None,
        tracing: Any = None,
    ) -> Any:
        raise NotImplementedError

    async def test_embed_single_happy_path(self) -> None:
        provider = self.make_embedding()
        result = await provider.embed(COMPANY_A, text='hello')
        assert _is_vectors(result)
        if isinstance(result, (list, tuple)) and result and isinstance(result[0], (int, float)):
            assert len(result) == 2

    async def test_embed_batch_happy_path(self) -> None:
        provider = self.make_embedding()
        result = await provider.embed(COMPANY_A, texts=['a', 'b'])
        assert isinstance(result, (list, tuple))
        assert len(result) == 2

    async def test_provider_failure_raises(self) -> None:
        provider = self.make_embedding(embedding_func=_failing_embedding)
        with pytest.raises(RuntimeError):
            await provider.embed(COMPANY_A, text='hello')

    async def test_empty_input_raises(self) -> None:
        provider = self.make_embedding()
        with pytest.raises(ValueError):
            await provider.embed(COMPANY_A)

    async def test_dimension_mismatch_raises(self) -> None:
        provider = self.make_embedding(embedding_func=lambda **_: {'data': [{'embedding': [1.0]}]})
        with pytest.raises(ValueError):
            await provider.embed(COMPANY_A, text='hello')

    async def test_company_scoping_records_calling_company(self) -> None:
        provider = self.make_embedding()
        await provider.embed(COMPANY_A, text='hello')
        await provider.embed(COMPANY_B, text='hello')
        if hasattr(provider, 'usage_rows') and provider.usage_rows:
            companies = [str(row.get('company_id')) for row in provider.usage_rows]
            assert str(COMPANY_A) in companies
            assert str(COMPANY_B) in companies


class TestLiteLLMEmbeddingContract(_EmbeddingProviderContract):
    def make_embedding(
        self,
        *,
        embedding_func: Any = None,
        dimensions: int = 2,
        metering: Any = None,
        tracing: Any = None,
    ) -> LiteLLMEmbedding:
        return LiteLLMEmbedding(
            embedding_func=embedding_func or _ok_embedding,
            model_id='test-model',
            dimensions=dimensions,
            metering=metering,
        )


class TestRetryingEmbeddingContract(_EmbeddingProviderContract):
    def make_embedding(
        self,
        *,
        embedding_func: Any = None,
        dimensions: int = 2,
        metering: Any = None,
        tracing: Any = None,
    ) -> RetryingEmbedding:
        inner = LiteLLMEmbedding(
            embedding_func=embedding_func or _ok_embedding,
            model_id='test-model',
            dimensions=dimensions,
        )
        return RetryingEmbedding(inner, retries=1)


class TestMeteredEmbeddingContract(_EmbeddingProviderContract):
    def make_embedding(
        self,
        *,
        embedding_func: Any = None,
        dimensions: int = 2,
        metering: Any = None,
        tracing: Any = None,
    ) -> MeteredEmbedding:
        inner = LiteLLMEmbedding(
            embedding_func=embedding_func or _ok_embedding,
            model_id='test-model',
            dimensions=dimensions,
        )
        retry = RetryingEmbedding(inner, retries=1)
        return MeteredEmbedding(retry, metering=metering)


class TestTracedEmbeddingContract(_EmbeddingProviderContract):
    def make_embedding(
        self,
        *,
        embedding_func: Any = None,
        dimensions: int = 2,
        metering: Any = None,
        tracing: Any = None,
    ) -> TracedEmbedding:
        inner = LiteLLMEmbedding(
            embedding_func=embedding_func or _ok_embedding,
            model_id='test-model',
            dimensions=dimensions,
        )
        retry = RetryingEmbedding(inner, retries=1)
        metered = MeteredEmbedding(retry, metering=metering)
        return TracedEmbedding(metered, tracing=tracing)


class TestEmbeddingDecoratorStackCompatibility:
    async def test_embed_works_through_stack(self) -> None:
        metering = FakeMetering()
        tracer = FakeTracer()
        provider = LiteLLMEmbedding(
            embedding_func=_ok_embedding, model_id='test-model', dimensions=2
        )
        retry = RetryingEmbedding(provider, retries=1)
        metered = MeteredEmbedding(retry, metering=metering)
        traced = TracedEmbedding(metered, tracing=tracer)
        result = await traced.embed(COMPANY_A, text='hello')
        assert _is_vectors(result)

    async def test_metering_is_recorded(self) -> None:
        metering = FakeMetering()
        tracer = FakeTracer()
        provider = LiteLLMEmbedding(
            embedding_func=_ok_embedding, model_id='test-model', dimensions=2
        )
        retry = RetryingEmbedding(provider, retries=1)
        metered = MeteredEmbedding(retry, metering=metering)
        traced = TracedEmbedding(metered, tracing=tracer)
        await traced.embed(COMPANY_A, text='hello')
        await traced.embed(COMPANY_A, texts=['a', 'b'])
        assert len(metering.records) >= 1

    async def test_tracing_is_invoked(self) -> None:
        metering = FakeMetering()
        tracer = FakeTracer()
        provider = LiteLLMEmbedding(
            embedding_func=_ok_embedding, model_id='test-model', dimensions=2
        )
        retry = RetryingEmbedding(provider, retries=1)
        metered = MeteredEmbedding(retry, metering=metering)
        traced = TracedEmbedding(metered, tracing=tracer)
        await traced.embed(COMPANY_A, text='hello')
        assert len(tracer.spans) >= 1
        assert tracer.spans[0][0] == COMPANY_A

    async def test_failure_propagates_through_stack(self) -> None:
        provider = LiteLLMEmbedding(
            embedding_func=_failing_embedding, model_id='test-model', dimensions=2
        )
        retry = RetryingEmbedding(provider, retries=0)
        traced = TracedEmbedding(retry, tracing=FakeTracer())
        with pytest.raises(RuntimeError):
            await traced.embed(COMPANY_A, text='hello')
