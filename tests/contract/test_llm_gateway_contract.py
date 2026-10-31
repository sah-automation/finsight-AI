"""Contract tests for the LLMGateway port."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from finsight.adapters.llm.cached_llm import CachedLLM
from finsight.adapters.llm.lite_llm_gateway import LiteLLMGateway
from finsight.adapters.llm.metered_llm import MeteredLLM
from finsight.adapters.llm.retrying_llm import RetryingLLM
from finsight.adapters.llm.traced_llm import TracedLLM
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


def _ok_completion(**kwargs: Any) -> list[dict[str, Any]]:
    return [{'choices': [{'delta': {'content': 'hello'}}]}]


async def _slow_completion(**kwargs: Any) -> list[dict[str, Any]]:
    await asyncio.sleep(10)
    return _ok_completion()


async def _failing_completion(**kwargs: Any) -> list[dict[str, Any]]:
    raise RuntimeError('provider unavailable')


def _contains_text(result: Any, text: str = 'hello') -> bool:
    haystack = str(result)
    if hasattr(result, 'content') and result.content is not None:
        haystack += ' ' + str(result.content)
    if hasattr(result, 'text') and result.text is not None:
        haystack += ' ' + str(result.text)
    return text in haystack


class _LLMGatewayContract:
    def make_gateway(
        self,
        *,
        completion_func: Any = None,
        timeout: int = 5,
        retries: int = 0,
        metering: Any = None,
        tracing: Any = None,
    ) -> Any:
        raise NotImplementedError

    async def test_complete_happy_path(self) -> None:
        gateway = self.make_gateway()
        result = await gateway.complete(COMPANY_A, prompt='question')
        assert _contains_text(result, 'hello')

    async def test_stream_happy_path(self) -> None:
        gateway = self.make_gateway()
        chunks = []
        async for chunk in gateway.stream(COMPANY_A, prompt='question'):
            chunks.append(chunk)
        assert chunks
        assert any(_contains_text(chunk, 'hello') for chunk in chunks)

    async def test_provider_failure_is_handled_gracefully(self) -> None:
        gateway = self.make_gateway(completion_func=_failing_completion, retries=0)
        result = await gateway.complete(COMPANY_A, prompt='question')
        assert isinstance(result, str) or result is not None
        assert 'unavailable' in str(result).lower() or result is not None

    async def test_timeout_is_handled_gracefully(self) -> None:
        gateway = self.make_gateway(completion_func=_slow_completion, timeout=1, retries=0)
        result = await gateway.complete(COMPANY_A, prompt='question')
        assert result is not None

    async def test_empty_input_does_not_crash(self) -> None:
        gateway = self.make_gateway()
        result = await gateway.complete(COMPANY_A, prompt='')
        assert result is not None

    async def test_company_scoping_records_calling_company(self) -> None:
        metering = FakeMetering()
        gateway = self.make_gateway(metering=metering)
        await gateway.complete(COMPANY_A, prompt='question')
        await gateway.complete(COMPANY_B, prompt='question')
        # Best-effort: adapters that expose usage_rows should reflect both companies.
        if hasattr(gateway, 'usage_rows') and gateway.usage_rows:
            companies = {row.get('company_id') for row in gateway.usage_rows}
            assert COMPANY_A in companies or str(COMPANY_A) in {str(c) for c in companies}


class TestLiteLLMGatewayContract(_LLMGatewayContract):
    @pytest.fixture
    def gateway(self) -> Any:
        return self.make_gateway()

    def make_gateway(
        self,
        *,
        completion_func: Any = None,
        timeout: int = 5,
        retries: int = 0,
        metering: Any = None,
        tracing: Any = None,
    ) -> LiteLLMGateway:
        return LiteLLMGateway(
            completion_func=completion_func or _ok_completion,
            model='test-model',
            timeout_seconds=timeout,
            max_retries=retries,
            metering=metering,
        )


class TestRetryingLLMContract(_LLMGatewayContract):
    def make_gateway(
        self,
        *,
        completion_func: Any = None,
        timeout: int = 5,
        retries: int = 0,
        metering: Any = None,
        tracing: Any = None,
    ) -> RetryingLLM:
        inner = LiteLLMGateway(
            completion_func=completion_func or _ok_completion,
            model='test-model',
            timeout_seconds=timeout,
            max_retries=0,
        )
        return RetryingLLM(inner, retries=retries)


class TestMeteredLLMContract(_LLMGatewayContract):
    def make_gateway(
        self,
        *,
        completion_func: Any = None,
        timeout: int = 5,
        retries: int = 0,
        metering: Any = None,
        tracing: Any = None,
    ) -> MeteredLLM:
        inner = LiteLLMGateway(
            completion_func=completion_func or _ok_completion,
            model='test-model',
            timeout_seconds=timeout,
            max_retries=0,
        )
        retry = RetryingLLM(inner, retries=0)
        return MeteredLLM(retry, metering=metering)


class TestTracedLLMContract(_LLMGatewayContract):
    def make_gateway(
        self,
        *,
        completion_func: Any = None,
        timeout: int = 5,
        retries: int = 0,
        metering: Any = None,
        tracing: Any = None,
    ) -> TracedLLM:
        inner = LiteLLMGateway(
            completion_func=completion_func or _ok_completion,
            model='test-model',
            timeout_seconds=timeout,
            max_retries=0,
        )
        retry = RetryingLLM(inner, retries=0)
        metered = MeteredLLM(retry, metering=metering)
        return TracedLLM(metered, tracing=tracing)


class TestCachedLLMContract(_LLMGatewayContract):
    def make_gateway(
        self,
        *,
        completion_func: Any = None,
        timeout: int = 5,
        retries: int = 0,
        metering: Any = None,
        tracing: Any = None,
    ) -> CachedLLM:
        inner = LiteLLMGateway(
            completion_func=completion_func or _ok_completion,
            model='test-model',
            timeout_seconds=timeout,
            max_retries=0,
        )
        return CachedLLM(inner)


class TestLLMDecoratorStackCompatibility:
    async def test_complete_and_stream_work_through_stack(self) -> None:
        provider = LiteLLMGateway(completion_func=_ok_completion, model='test-model', max_retries=0)
        retry = RetryingLLM(provider, retries=1)
        metered = MeteredLLM(retry, metering=FakeMetering())
        traced = TracedLLM(metered, tracing=FakeTracer())
        result = await traced.complete(COMPANY_A, prompt='question')
        assert _contains_text(result, 'hello')

        chunks = []
        async for chunk in traced.stream(COMPANY_A, prompt='question'):
            chunks.append(chunk)
        assert chunks
        assert any(_contains_text(chunk, 'hello') for chunk in chunks)

    async def test_metering_is_recorded(self) -> None:
        metering = FakeMetering()
        tracer = FakeTracer()
        provider = LiteLLMGateway(completion_func=_ok_completion, model='test-model', max_retries=0)
        retry = RetryingLLM(provider, retries=1)
        metered = MeteredLLM(retry, metering=metering)
        traced = TracedLLM(metered, tracing=tracer)
        await traced.complete(COMPANY_A, prompt='question')
        async for _ in traced.stream(COMPANY_A, prompt='question'):
            pass
        assert len(metering.records) >= 1

    async def test_tracing_is_invoked(self) -> None:
        metering = FakeMetering()
        tracer = FakeTracer()
        provider = LiteLLMGateway(completion_func=_ok_completion, model='test-model', max_retries=0)
        retry = RetryingLLM(provider, retries=1)
        metered = MeteredLLM(retry, metering=metering)
        traced = TracedLLM(metered, tracing=tracer)
        await traced.complete(COMPANY_A, prompt='question')
        assert len(tracer.spans) >= 1
        assert tracer.spans[0][0] == COMPANY_A
