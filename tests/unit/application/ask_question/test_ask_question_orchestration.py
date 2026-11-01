"""Behavioral tests for Q&A orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.application.ask_question import AskQuestion
from finsight.core.config.loader import load_config
from finsight.core.types import CompanyId, RequestContext, Role, TraceId, UserId


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
    async def search(self, query: Any = None, embedding: Any = None, **kwargs: Any) -> Any:
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


def test_ask_question_success_path() -> None:
    _cfg = load_config('test')
    orchestrator = AskQuestion(
        config=_cfg,
        llm_gateway=_LLM(),
        embedding_provider=_Embedding(),
        hybrid_search=_Search(),
        reranker=_Reranker(),
        metric_repository=_Metrics(),
        answer_cache=_Cache(),
        waiting_line=_Waiting(),
        tracing=_Tracing(),
        signing_key='secret-key-1234567890',
    )
    _ctx = RequestContext(
        company_id=CompanyId('co1'),
        user_id=UserId('u1'),
        role=Role.EXECUTIVE_LEADERSHIP,
        trace_id=TraceId('t1'),
        permissions={},
        access_scope=[],
    )
    result = asyncio.run(orchestrator.run(_ctx, 'Why did margins fall?'))
    assert getattr(result, 'answer', None) == 'Margins fell because costs rose.'
    citations = getattr(result, 'citations', [])
    assert len(citations) == 1


def test_ask_question_unavailable_path() -> None:
    _cfg = load_config('test')
    orchestrator = AskQuestion(
        config=_cfg,
        llm_gateway=_LLM(answer=None),
        embedding_provider=_Embedding(),
        hybrid_search=_Search(),
        reranker=_Reranker(),
        metric_repository=_Metrics(),
        answer_cache=_Cache(),
        waiting_line=_Waiting(),
        tracing=_Tracing(),
        signing_key='secret-key-1234567890',
    )
    _ctx = RequestContext(
        company_id=CompanyId('co1'),
        user_id=UserId('u1'),
        role=Role.EXECUTIVE_LEADERSHIP,
        trace_id=TraceId('t1'),
        permissions={},
        access_scope=[],
    )
    result = asyncio.run(orchestrator.run(_ctx, 'Why did margins fall?'))
    assert getattr(result, 'answer', None) in (None, '')
    class_name = type(result).__name__
    assert 'Unavailable' in class_name or getattr(result, 'answer', None) is None
