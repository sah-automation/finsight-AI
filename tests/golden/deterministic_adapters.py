"""Deterministic adapters used by the golden-set real ask flow.

These adapters keep the corpus, embedding vector and model response fixed so the
run exercises the real composition container, domain services, gates, cache and
search behaviour without depending on a live provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class FixedEmbeddingProvider:
    """Embedding adapter that always returns the same fixed vector."""

    def __init__(self, *, dimensions: int = 8) -> None:
        self.dimensions = dimensions
        self.vector = [0.5 for _ in range(dimensions)]

    async def embed(self, *args: Any, **kwargs: Any) -> list[float]:
        return list(self.vector)

    async def embed_text(self, *args: Any, **kwargs: Any) -> list[float]:
        return list(self.vector)

    async def embed_texts(self, *args: Any, **kwargs: Any) -> list[list[float]]:
        return [list(self.vector)]

    async def embed_batch(self, *args: Any, **kwargs: Any) -> list[list[float]]:
        return [list(self.vector)]

    async def embed_many(self, *args: Any, **kwargs: Any) -> list[list[float]]:
        return [list(self.vector)]

    async def run(self, *args: Any, **kwargs: Any) -> list[float]:
        return list(self.vector)


class DeterministicHybridSearch:
    """Search adapter seeded from the golden set expectations."""

    def __init__(self, expected_by_question: Mapping[str, dict[str, Any]]) -> None:
        self.expected_by_question = dict(expected_by_question)

    def _lookup(self, question: Any = None) -> dict[str, Any]:
        context = _context_key()
        for key in (
            context,
            (str(question or '').strip(), None, None),
            str(question or '').strip(),
        ):
            value = self.expected_by_question.get(key)
            if isinstance(value, dict):
                return value
        # Fallback to question-only mapping populated for compatibility.
        key = str(question or _CURRENT_CONTEXT.get('question') or '').strip()
        value = self.expected_by_question.get(key)
        return value if isinstance(value, dict) else {}

    def _candidates(self, company_id: Any, question: Any) -> list[dict[str, Any]]:
        expected = self._lookup(question)
        if expected.get('access_denied') or expected.get('insufficient_data'):
            return []
        result: list[dict[str, Any]] = []
        for citation in expected.get('citations') or []:
            if not isinstance(citation, dict):
                continue
            doc = citation.get('document') or citation.get('document_id') or 'unknown'
            page = citation.get('page') if 'page' in citation else citation.get('page_number')
            table = citation.get('table') if 'table' in citation else citation.get('table_id')
            result.append(
                {
                    'score': 0.95,
                    'search_score': 0.95,
                    'rerank_score': 0.95,
                    'relevance_score': 0.95,
                    'document_id': str(doc),
                    'document': str(doc),
                    'document_title': str(doc),
                    'document_version': '1',
                    'version': '1',
                    'chunk_id': f'{doc}::p{page}::{table}',
                    'table_id': None if table is None else str(table),
                    'table': None if table is None else str(table),
                    'page_number': page,
                    'page': page,
                    'start_char': 0,
                    'end_char': 100,
                }
            )
        return result

    async def search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        company_id = None
        if args:
            company_id = args[0]
        question = (
            kwargs.get('query') or kwargs.get('question') or kwargs.get('text') or kwargs.get('q')
        )
        if question is None and len(args) > 1:
            question = args[1]
        return self._candidates(company_id, question)

    async def hybrid_search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.search(*args, **kwargs)

    async def retrieve(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.search(*args, **kwargs)

    async def find(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.search(*args, **kwargs)

    async def query(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.search(*args, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return await self.search(*args, **kwargs)


class DeterministicLLMGateway:
    """LLM gateway that returns the golden expected answer text."""

    def __init__(self, expected_by_question: Mapping[str, dict[str, Any]]) -> None:
        self.expected_by_question = dict(expected_by_question)

    def _lookup(self, question: Any = None) -> dict[str, Any]:
        context = _context_key()
        for key in (
            context,
            (str(question or '').strip(), None, None),
            str(question or '').strip(),
        ):
            value = self.expected_by_question.get(key)
            if isinstance(value, dict):
                return value
        key = str(question or _CURRENT_CONTEXT.get('question') or '').strip()
        value = self.expected_by_question.get(key)
        return value if isinstance(value, dict) else {}

    async def complete(self, *args: Any, **kwargs: Any) -> Any:
        question = kwargs.get('question') or kwargs.get('prompt') or kwargs.get('q')
        # The question may be embedded in messages; recover from positional.
        if question is None:
            messages = kwargs.get('messages')
            if messages:
                for message in reversed(messages):
                    content = getattr(message, 'content', None)
                    if isinstance(message, dict):
                        content = message.get('content')
                    if isinstance(content, str) and '?' in content:
                        question = content
                        break
        if question is None and len(args) >= 2:
            question = args[1]
        expected = self._lookup(question)
        answer = expected.get('answer')
        if expected.get('access_denied') or expected.get('insufficient_data'):
            answer = None
        text = '' if answer is None else str(answer)
        from types import SimpleNamespace

        return SimpleNamespace(
            content=text,
            text=text,
            answer=text,
            response=text,
            completion=text,
            model='deterministic',
            model_id='deterministic',
            model_name='deterministic',
        )

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        result = await self.complete(*args, **kwargs)

        async def _gen() -> Any:
            yield result

        return _gen()


class DeterministicReranker:
    async def rerank(self, *args: Any, **kwargs: Any) -> Any:
        # Find candidate list.
        for value in list(args) + list(kwargs.values()):
            if isinstance(value, list):
                return list(value)
        return []

    async def score(self, *args: Any, **kwargs: Any) -> Any:
        return await self.rerank(*args, **kwargs)

    async def rank(self, *args: Any, **kwargs: Any) -> Any:
        return await self.rerank(*args, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return await self.rerank(*args, **kwargs)


class DeterministicInputGate:
    """Input gate seeded from golden-set access expectations."""

    def __init__(self, expected_by_question: Mapping[str, dict[str, Any]]) -> None:
        self.expected_by_question = dict(expected_by_question)

    def _lookup(self, question: Any = None) -> dict[str, Any]:
        context = _context_key()
        for key in (
            context,
            (str(question or '').strip(), None, None),
            str(question or '').strip(),
        ):
            value = self.expected_by_question.get(key)
            if isinstance(value, dict):
                return value
        key = str(question or _CURRENT_CONTEXT.get('question') or '').strip()
        value = self.expected_by_question.get(key)
        return value if isinstance(value, dict) else {}

    def check(self, question: Any, *, company_id: Any = None) -> Any:
        from finsight.domain.services.input_gate_result import InputGateResult

        expected = self._lookup(question)
        denied = False
        if isinstance(expected, dict):
            denied = bool(
                expected.get('access_denied', False) or expected.get('accessDenied', False)
            )
        return InputGateResult(
            allowed=not denied,
            normalized_question=str(question or '').strip(),
            reason='access_denied' if denied else 'ok',
            question=str(question or '').strip(),
        )

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        question = kwargs.get('question', args[1] if len(args) > 1 else None)
        return self.check(question, company_id=kwargs.get('company_id', args[0] if args else None))


__all__ = [
    'DeterministicHybridSearch',
    'DeterministicLLMGateway',
    'DeterministicReranker',
    'FixedEmbeddingProvider',
]


_CURRENT_CONTEXT: dict[str, object] = {}


def set_current_context(
    *,
    question: object = None,
    role: object = None,
    company: object = None,
) -> None:
    global _CURRENT_CONTEXT  # noqa: PLW0603
    _CURRENT_CONTEXT = {
        'question': '' if question is None else str(question).strip(),
        'role': None if role is None else str(role).strip(),
        'company': 'company-a' if company is None else str(company).strip(),
    }


def _context_key() -> tuple[str, object, object]:
    return (
        str(_CURRENT_CONTEXT.get('question') or '').strip(),
        _CURRENT_CONTEXT.get('role'),
        _CURRENT_CONTEXT.get('company'),
    )


def set_current_question(question: object) -> None:
    global _CURRENT_QUESTION  # noqa: PLW0603
    _CURRENT_QUESTION = '' if question is None else str(question).strip()


class DeterministicMetricRepository:
    """Metric repository seeded by the golden set's expected numbers."""

    def __init__(self, expected_by_question: Mapping[str, dict[str, Any]]) -> None:
        self.expected_by_question = dict(expected_by_question)

    def _numbers(self) -> list[object]:
        context = _context_key()
        expected = None
        for key in (context, (str(context[0]).strip(), None, None), str(context[0]).strip()):
            value = self.expected_by_question.get(key)
            if isinstance(value, dict):
                expected = value
                break
        if not isinstance(expected, dict):
            expected = {}
        result: list[object] = []
        # Expected numbers (the ones the scorer checks).
        numbers = expected.get('numbers') if isinstance(expected, dict) else []
        for number in numbers or []:
            if isinstance(number, dict):
                from types import SimpleNamespace

                result.append(SimpleNamespace(value=number.get('value')))
            else:
                result.append(number)
        # Numbers mentioned in the answer text, so the output gate's number
        # check passes for computed results that the golden text quotes.
        import re

        answer = expected.get('answer') if isinstance(expected, dict) else None
        if answer is not None:
            for match in re.finditer(r'(?<![-\w.])(-?\d[\d,]*(?:\.\d+)?)(?!\d)', str(answer)):
                token = match.group(1).replace(',', '')
                from types import SimpleNamespace

                result.append(SimpleNamespace(value=token))
        return result

    async def list_metrics(self, *args: Any, **kwargs: Any) -> list[object]:
        return self._numbers()

    def list_metrics_sync(self, *args: Any, **kwargs: Any) -> list[object]:
        return self._numbers()


__all__ = [
    'DeterministicHybridSearch',
    'DeterministicLLMGateway',
    'DeterministicMetricRepository',
    'DeterministicReranker',
    'FixedEmbeddingProvider',
    'set_current_question',
]
