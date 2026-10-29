"""Contract tests for the Reranker port."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from finsight.adapters.rerank.cohere_reranker import CohereReranker
from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from finsight.domain.ports import Reranker

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')


class _Scorer:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[list[str]] = []

    async def rerank(self, query: str, documents: list[dict[str, Any]], **kwargs: Any) -> list[Any]:
        self.calls.append([document['text'] for document in documents])
        return [
            {'index': index, 'relevance_score': self.scores[document['text']]}
            for index, document in enumerate(documents)
        ]


class _BrokenScorer:
    async def rerank(self, *args: Any, **kwargs: Any) -> list[Any]:
        raise RuntimeError('provider unavailable')


class _SlowScorer:
    async def rerank(self, *args: Any, **kwargs: Any) -> list[Any]:
        await asyncio.sleep(10)
        return []


def _candidates() -> list[dict[str, Any]]:
    return [
        {'chunk_id': 'c1', 'company_id': str(COMPANY), 'text': 'Revenue was 100.'},
        {'chunk_id': 'c2', 'company_id': str(COMPANY), 'text': 'Profit was 20.'},
        {'chunk_id': 'c3', 'company_id': str(COMPANY), 'text': 'Debt was 40.'},
        {'chunk_id': 'c4', 'company_id': str(OTHER_COMPANY), 'text': 'Revenue was 900.'},
    ]


def _config(**overrides: Any) -> SimpleNamespace:
    reranker = SimpleNamespace(
        provider='cohere',
        model='rerank-test',
        top_n=20,
        timeout_seconds=overrides.pop('timeout_seconds', 1),
        max_retries=overrides.pop('max_retries', 0),
        batch_size=overrides.pop('batch_size', 2),
    )
    retrieval = SimpleNamespace(
        evidence_min_score=0.30,
        evidence_min_search_score=0.50,
        evidence_min_chunks=1,
    )
    switches = SimpleNamespace(reranker_enabled=overrides.pop('reranker_enabled', True))
    return SimpleNamespace(reranker=reranker, retrieval=retrieval, switches=switches)


@pytest.fixture
def reranker() -> Reranker:
    scorer = _Scorer({'Revenue was 100.': 0.2, 'Profit was 20.': 0.9, 'Debt was 40.': 0.5})
    return CohereReranker(client=scorer, config=_config())


class TestRerankerContract:
    async def test_batches_candidates_and_orders_by_score(self, reranker: Reranker) -> None:
        scorer = reranker.client  # type: ignore[attr-defined]

        result = await reranker.rerank(
            COMPANY, question='Which was profit?', candidates=_candidates()
        )

        assert [candidate['chunk_id'] for candidate in result] == ['c2', 'c3', 'c1']
        assert len(scorer.calls) == 2
        assert all(len(batch) <= 2 for batch in scorer.calls)
        assert result.fallback is False
        assert result.threshold == 0.30
        assert result[0]['rerank_score'] == 0.9

    async def test_tenant_isolation_filters_other_companies(self, reranker: Reranker) -> None:
        result = await reranker.rerank(
            COMPANY, question='Which was profit?', candidates=_candidates()
        )

        assert all(candidate['company_id'] == str(COMPANY) for candidate in result)
        assert 'c4' not in [candidate['chunk_id'] for candidate in result]

    async def test_failure_falls_back_to_search_order_and_marks_trace(self) -> None:
        reranker = CohereReranker(client=_BrokenScorer(), config=_config(max_retries=1))

        result = await reranker.rerank(
            COMPANY, question='Which was profit?', candidates=_candidates()
        )

        assert [candidate['chunk_id'] for candidate in result] == ['c1', 'c2', 'c3']
        assert result.fallback is True
        assert result.fallback_mode == 'search_order'
        assert result.threshold == 0.50
        assert result.trace['reranker_fallback'] is True
        assert result.trace['evidence_threshold'] == 0.50

    async def test_timeout_falls_back_to_search_order(self) -> None:
        reranker = CohereReranker(client=_SlowScorer(), config=_config(timeout_seconds=1))

        result = await reranker.rerank(
            COMPANY, question='Which was profit?', candidates=_candidates()
        )

        assert [candidate['chunk_id'] for candidate in result] == ['c1', 'c2', 'c3']
        assert result.fallback is True
        assert result.threshold == 0.50

    async def test_switch_off_uses_search_order_and_search_threshold(self) -> None:
        scorer = _Scorer({'Revenue was 100.': 0.2, 'Profit was 20.': 0.9, 'Debt was 40.': 0.5})
        reranker = CohereReranker(client=scorer, config=_config(reranker_enabled=False))

        result = await reranker.rerank(
            COMPANY, question='Which was profit?', candidates=_candidates()
        )

        assert [candidate['chunk_id'] for candidate in result] == ['c1', 'c2', 'c3']
        assert scorer.calls == []
        assert result.fallback is True
        assert result.disabled is True
        assert result.threshold == 0.50

    async def test_empty_candidates_returns_empty_result(self, reranker: Reranker) -> None:
        result = await reranker.rerank(COMPANY, question='anything', candidates=[])

        assert list(result) == []
        assert result.fallback is False

    async def test_requires_company_id(self, reranker: Reranker) -> None:
        with pytest.raises((TypeError, ValueError)):
            await reranker.rerank(None, question='anything', candidates=_candidates())  # type: ignore[arg-type]
