"""Contract tests: ask-question flow produces a complete, correlated trace (#288).

Proves that a real question flow emits one trace per HTTP request: step spans
with durations, a correlated LLM span with non-zero durations and token counts,
all sharing the originating ``X-Request-ID`` trace id, and active switch values
on every span. Dev content capture is visible when the switch is on.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.adapters.llm.traced_llm import TracedLLM
from finsight.adapters.tracing.tracing_adapter import TracingAdapter
from finsight.application.ask_question import AskQuestion
from finsight.core.config import load_config
from finsight.core.logging.context import bind_request_context, reset_request_context
from finsight.core.types import CompanyId, RequestContext, Role, TraceId, UserId

pytestmark = pytest.mark.contract

COMPANY = CompanyId('co-1')
TRACE_ID = 'req-123'


def _trace_id_of(span: Any) -> Any:
    """Trace id is carried either on the span field or in attributes, depending on the emitter."""
    return span.trace_id or span.attributes.get('trace_id')


class _FakeLLM:
    """Inner LLM that returns a usage-carrying completion dict."""

    model = 'test-model'

    async def complete(self, company_id: Any = None, **kwargs: Any) -> Any:
        return {
            'content': 'Margins fell because costs rose.',
            'model': 'test-model',
            'usage': {'prompt_tokens': 14, 'completion_tokens': 6, 'total_tokens': 20},
        }


class _FakeEmbedding:
    async def embed(self, company_id: Any = None, **kwargs: Any) -> Any:
        return [0.1, 0.2]


class _FakeSearch:
    async def search(self, company_id: Any = None, **kwargs: Any) -> Any:
        return [
            {
                'document_id': 'doc-1',
                'document_version': 'v1',
                'page_number': 4,
                'text': 'Revenue grew 12 percent year over year.',
                'score': 0.9,
            }
        ]


class _FakeReranker:
    async def rerank(self, company_id: Any = None, **kwargs: Any) -> Any:
        return [
            {
                'document_id': 'doc-1',
                'document_version': 'v1',
                'page_number': 4,
                'text': 'Revenue grew 12 percent year over year.',
                'score': 0.9,
            }
        ]


class _FakeMetrics:
    async def list_metrics(self, *args: Any, **kwargs: Any) -> Any:
        return []


class _FakeCache:
    async def get(self, *args: Any, **kwargs: Any) -> Any:
        return None

    async def set(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _FakeWaiting:
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        work = kwargs.get('work')
        if work is None and len(args) >= 2:
            work = args[1]
        if callable(work):
            result = work()
            if asyncio.iscoroutine(result):
                return await result
            return result
        return None


def _build_orchestrator(tracing: Any, config: Any) -> AskQuestion:
    inner = _FakeLLM()
    traced = TracedLLM(inner, tracing=tracing, config=config)
    # Mirror production wiring: config is reachable through the inner gateway so
    # switch values and the content-capture switch resolve through the decorator.
    traced.config = config
    return AskQuestion(
        config=config,
        llm_gateway=traced,
        embedding_provider=_FakeEmbedding(),
        hybrid_search=_FakeSearch(),
        reranker=_FakeReranker(),
        metric_repository=_FakeMetrics(),
        answer_cache=_FakeCache(),
        waiting_line=_FakeWaiting(),
        tracing=tracing,
        signing_key='secret-key-1234567890',
    )


def _context() -> RequestContext:
    return RequestContext(
        company_id=COMPANY,
        user_id=UserId('u1'),
        role=Role.EXECUTIVE_LEADERSHIP,
        trace_id=TraceId(TRACE_ID),
        permissions={},
        access_scope=[],
    )


def _llm_span(spans: list[Any]) -> Any:
    llm_spans = [s for s in spans if isinstance(s.attributes.get('tokens_total'), int)]
    assert llm_spans, 'expected an LLM span carrying token counts'
    return llm_spans[0]


def test_question_flow_emits_complete_correlated_trace() -> None:
    """A question flow produces step spans + an LLM span sharing one trace id."""
    config = load_config('test')
    tracer = TracingAdapter(config=config, service_name='test', enabled=True)
    orchestrator = _build_orchestrator(tracing=tracer, config=config)

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        result = asyncio.run(orchestrator.run(_context(), 'What was revenue growth?'))
        assert getattr(result, 'answer', None) == 'Margins fell because costs rose.'

        spans = tracer.emitted_spans(COMPANY)
        assert spans, 'expected at least one emitted span'

        # Every span shares the originating X-Request-ID trace id.
        for span in spans:
            assert _trace_id_of(span) == TRACE_ID, (
                f'span {span.name!r} does not carry the request trace id'
            )
            assert isinstance(span.attributes.get('duration_ms'), (int, float))
            assert span.attributes.get('duration_ms', 0) > 0
            assert 'active_switch_values' in span.attributes, (
                f'span {span.name!r} missing active switch tags'
            )

        # One trace per request: an LLM span with real duration and token counts.
        llm = _llm_span(spans)
        assert llm.attributes.get('duration_ms', 0) > 0
        assert llm.attributes.get('tokens_total', 0) > 0
        assert llm.attributes.get('tokens_prompt', 0) > 0
        assert llm.attributes.get('tokens_completion', 0) > 0
        assert llm.attributes.get('model_name') == 'test-model'
        assert _trace_id_of(llm) == TRACE_ID

        # Orchestration step spans are present with durations.
        step_names = {s.name for s in spans}
        assert {'input_gate', 'model_generation'} & step_names
    finally:
        reset_request_context(tokens)


def _config(capture: bool) -> SimpleNamespace:
    return SimpleNamespace(
        switches=SimpleNamespace(
            llm_content_capture_enabled=capture,
            answer_cache_enabled=True,
            parallel_steps=True,
            detailed_tracing_enabled=True,
            usage_metering_enabled=True,
        )
    )


def test_question_flow_content_capture_visible_in_dev() -> None:
    """With capture on (dev default), the LLM span carries prompt/response content."""
    config = _config(True)
    tracer = TracingAdapter(config=config, service_name='test', enabled=True)
    orchestrator = _build_orchestrator(tracing=tracer, config=config)

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        asyncio.run(orchestrator.run(_context(), 'What was revenue growth?'))
    finally:
        reset_request_context(tokens)

    llm = _llm_span(tracer.emitted_spans(COMPANY))
    serialized = str(llm.attributes)
    assert 'gen_ai.prompt.messages' in serialized or 'gen_ai.completion.messages' in serialized


def test_question_flow_switch_off_removes_content_keeps_telemetry() -> None:
    """Turning capture off drops prompt/response content but keeps tokens/latency."""
    config = _config(False)
    tracer = TracingAdapter(config=config, service_name='test', enabled=True)
    orchestrator = _build_orchestrator(tracing=tracer, config=config)

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        asyncio.run(orchestrator.run(_context(), 'What was revenue growth?'))
    finally:
        reset_request_context(tokens)

    llm = _llm_span(tracer.emitted_spans(COMPANY))
    serialized = str(llm.attributes)
    assert 'gen_ai.prompt.messages' not in serialized
    assert 'gen_ai.completion.messages' not in serialized
    # Aggregate telemetry remains.
    assert isinstance(llm.attributes.get('tokens_total'), int)
    assert llm.attributes.get('tokens_total', 0) > 0
    assert isinstance(llm.attributes.get('duration_ms'), (int, float))
    assert llm.attributes.get('duration_ms', 0) > 0
