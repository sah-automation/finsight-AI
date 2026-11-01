"""Behavioral tests for Q&A orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

from finsight.application.ask_question import AskQuestion


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


def test_ask_question_success_path() -> None:
    orchestrator = AskQuestion(
        llm_gateway=_LLM(), search=_Search(), signing_key='secret-key-1234567890'
    )
    result = asyncio.run(orchestrator.run(company_id='co1', question='Why did margins fall?'))
    assert getattr(result, 'answer', None) == 'Margins fell because costs rose.'
    citations = getattr(result, 'citations', [])
    assert len(citations) == 1


def test_ask_question_unavailable_path() -> None:
    orchestrator = AskQuestion(
        llm_gateway=_LLM(answer=None), search=_Search(), signing_key='secret-key-1234567890'
    )
    result = asyncio.run(orchestrator.run(company_id='co1', question='Why did margins fall?'))
    assert getattr(result, 'answer', None) in (None, '')
    class_name = type(result).__name__
    assert 'Unavailable' in class_name or getattr(result, 'answer', None) is None
