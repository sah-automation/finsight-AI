"""Span completion tests for the ask-question orchestrator (#286).

Verifies that every orchestrator step emits a completion span after the step
runs, carrying ``duration_ms`` and ``outcome``, sharing the request trace ID,
and that failed steps still emit a failure span.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from finsight.adapters.tracing.disabled_tracer import DisabledTracer
from finsight.application.ask_question import AskQuestion
from finsight.core.config import load_config
from finsight.core.logging.context import bind_request_context, reset_request_context
from finsight.core.types import CompanyId, RequestContext, Role, TraceId, UserId

pytestmark = pytest.mark.unit

COMPANY = CompanyId('co1')
TRACE_ID = 't1'


class _LLM:
    def __init__(self, answer: str | None = 'Margins fell because costs rose.') -> None:
        self.answer = answer

    async def complete(
        self,
        company_id: Any,
        messages: Any = None,
        prompt: Any = None,
        question: Any = None,
        **kwargs: Any,
    ) -> Any:
        if self.answer is None:
            return None

        class _Result:
            content = None

        result = _Result()
        result.content = self.answer
        result.model = 'primary-model'
        return result


class _Search:
    async def search(self, company_id: Any = None, *args: Any, **kwargs: Any) -> Any:
        return [{'document_id': 'doc1', 'document_version': 'v1', 'page_number': 4, 'score': 0.9}]


class _Embedding:
    async def embed(self, *args: Any, **kwargs: Any) -> Any:
        return [0.1, 0.2]


class _Reranker:
    async def rerank(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _Metrics:
    async def list_metrics(self, *args: Any, **kwargs: Any) -> Any:
        return []


class _Cache:
    async def get(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _Waiting:
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


def _build_orchestrator(tracing: Any, llm: _LLM | None = None) -> AskQuestion:
    return AskQuestion(
        config=load_config('test'),
        llm_gateway=llm or _LLM(),
        embedding_provider=_Embedding(),
        hybrid_search=_Search(),
        reranker=_Reranker(),
        metric_repository=_Metrics(),
        answer_cache=_Cache(),
        waiting_line=_Waiting(),
        tracing=tracing,
        signing_key='secret-key-1234567890',
    )


def _context() -> RequestContext:
    return RequestContext(
        company_id=COMPANY,
        user_id=UserId('u1'),
        role=Role.EXECUTIVE_LEADERSHIP,
        trace_id=TraceId('t1'),
        permissions={},
        access_scope=[],
    )


def _last_span(tracer: DisabledTracer) -> Any:
    spans = tracer.emitted_spans(COMPANY)
    assert spans, 'expected at least one emitted span'
    return spans[-1]


def test_ask_question_emits_completion_spans_with_duration_and_outcome() -> None:
    tracer = DisabledTracer()
    orchestrator = _build_orchestrator(tracing=tracer)

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        result = asyncio.run(orchestrator.run(_context(), 'Why did margins fall?'))
        assert getattr(result, 'answer', None) == 'Margins fell because costs rose.'

        spans = tracer.emitted_spans(COMPANY)
        assert spans, 'expected at least one span'
        # Each step span must carry duration_ms and outcome.
        for span in spans:
            attrs = span.attributes
            assert isinstance(attrs.get('duration_ms'), (int, float)), (
                f'missing duration_ms in {span.name}'
            )
            assert attrs.get('duration_ms', 0) > 0
            assert attrs.get('outcome') == 'success'
            assert attrs.get('trace_id') == TRACE_ID
    finally:
        reset_request_context(tokens)


def test_ask_question_failed_step_emits_failure_span() -> None:
    """An input-gate failure must still produce a span with outcome='failure'."""

    class _BlockingGate:
        def check(self, question: str, company_id: Any) -> Any:
            raise RuntimeError('input gate blocked')

    tracer = DisabledTracer()
    orchestrator = AskQuestion(
        config=load_config('test'),
        llm_gateway=_LLM(),
        embedding_provider=_Embedding(),
        hybrid_search=_Search(),
        reranker=_Reranker(),
        metric_repository=_Metrics(),
        answer_cache=_Cache(),
        waiting_line=_Waiting(),
        tracing=tracer,
        signing_key='secret-key-1234567890',
    )
    # Replace the input gate with a blocking one.
    orchestrator._input_gate = _BlockingGate()

    tokens = bind_request_context(TRACE_ID, str(COMPANY), 'u1')
    try:
        with pytest.raises(RuntimeError):
            asyncio.run(orchestrator.run(_context(), 'Why did margins fall?'))

        spans = tracer.emitted_spans(COMPANY)
        # At least the input_gate step must have emitted a failure span.
        gate_spans = [s for s in spans if s.name == 'input_gate']
        assert gate_spans, 'expected an input_gate span'
        assert gate_spans[-1].attributes.get('outcome') == 'failure'
        assert isinstance(gate_spans[-1].attributes.get('duration_ms'), (int, float))
        assert gate_spans[-1].attributes.get('duration_ms', 0) > 0
    finally:
        reset_request_context(tokens)


def test_ask_question_without_tracer_still_works() -> None:
    orchestrator = _build_orchestrator(tracing=None)
    result = asyncio.run(orchestrator.run(_context(), 'Why did margins fall?'))
    assert getattr(result, 'answer', None) == 'Margins fell because costs rose.'
