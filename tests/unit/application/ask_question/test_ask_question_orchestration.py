"""Behavioral tests for Q&A orchestration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from finsight.application.ask_question import AskQuestion
from finsight.core.config.loader import load_config
from finsight.core.types import CompanyId, RequestContext, Role, TraceId, UserId


class _LLM:
    def __init__(self, answer: str | None = 'Margins fell because costs rose.') -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        company_id: Any,
        messages: Any = None,
        prompt: Any = None,
        question: Any = None,
        **kwargs: Any,
    ) -> Any:
        self.calls.append({'messages': messages, 'prompt': prompt, 'question': question, **kwargs})
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
    def __init__(self, broken: bool = False) -> None:
        self._broken = broken

    async def embed(self, *args: Any, **kwargs: Any) -> Any:
        if self._broken:
            raise RuntimeError('embedding provider unavailable')
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

    async def set(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _Waiting:
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        # Invoke the submitted work directly.
        work = kwargs.get('work')
        if work is None and len(args) >= 2:
            # positional work may be second arg
            work = args[1]
        if callable(work):
            result = work()
            if asyncio.iscoroutine(result):
                return await result
            return result
        return None


class _Tracing:
    async def start_span(self, *args: Any, **kwargs: Any) -> Any:
        return None


def _build_orchestrator(
    llm: _LLM,
    *,
    embedding_provider: Any | None = None,
) -> AskQuestion:
    if embedding_provider is None:
        embedding_provider = _Embedding()
    return AskQuestion(
        config=load_config('test'),
        llm_gateway=llm,
        embedding_provider=embedding_provider,
        hybrid_search=_Search(),
        reranker=_Reranker(),
        metric_repository=_Metrics(),
        answer_cache=_Cache(),
        waiting_line=_Waiting(),
        tracing=_Tracing(),
        signing_key='secret-key-1234567890',
    )


def _context() -> RequestContext:
    return RequestContext(
        company_id=CompanyId('co1'),
        user_id=UserId('u1'),
        role=Role.EXECUTIVE_LEADERSHIP,
        trace_id=TraceId('t1'),
        permissions={},
        access_scope=[],
    )


def test_ask_question_success_path() -> None:
    orchestrator = _build_orchestrator(_LLM())
    result = asyncio.run(orchestrator.run(_context(), 'Why did margins fall?'))
    assert getattr(result, 'answer', None) == 'Margins fell because costs rose.'
    citations = getattr(result, 'citations', [])
    assert len(citations) == 1


def test_ask_question_unavailable_path() -> None:
    orchestrator = _build_orchestrator(_LLM(answer=None))
    result = asyncio.run(orchestrator.run(_context(), 'Why did margins fall?'))
    assert getattr(result, 'answer', None) in (None, '')
    class_name = type(result).__name__
    assert 'Unavailable' in class_name or getattr(result, 'answer', None) is None


def test_embed_degradation_warns_with_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An embed failure must be logged with the exception before degrading."""
    orchestrator = _build_orchestrator(_LLM(), embedding_provider=_Embedding(broken=True))

    with caplog.at_level(logging.WARNING, logger='finsight.application.ask_question'):
        result = asyncio.run(orchestrator.run(_context(), 'Why did margins fall?'))

    records = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and 'embedding' in r.message.lower()
    ]
    assert records
    assert all(r.exc_info is not None for r in records)
    # Degradation contract unchanged: the flow still produces an answer.
    assert getattr(result, 'answer', None) == 'Margins fell because costs rose.'


@pytest.mark.parametrize(
    ('question', 'expected_chain'),
    [
        ('What happened to revenue?', 'cheap'),
        ('Calculate the total margin', 'primary'),
    ],
)
def test_ask_question_passes_router_tier_to_gateway(question: str, expected_chain: str) -> None:
    llm = _LLM()
    asyncio.run(_build_orchestrator(llm).run(_context(), question))

    assert llm.calls
    assert llm.calls[-1]['chain'] == expected_chain
