# mypy: disable-error-code="misc,method-assign,no-untyped-def,arg-type,attr-defined"
"""Cross-encoder reranker with a safe search-order fallback."""

from __future__ import annotations

from typing import Any

from finsight.domain.ports.reranker import Reranker as RerankerPort

from ._rerank_helpers import *  # noqa: F403
from ._rerank_operations import (
    _batch_count,
    _call_scorer,
    _fallback,
    _init_reranker,
    _parse,
    _rerank,
    _result,
    _score,
    _score_batch,
    _scorer_attempts,
    _tenant_candidates,
)


class CohereReranker(RerankerPort):
    """Score candidates in batches and fall back to search order on failure."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _init_reranker(self, *args, **kwargs)

    async def rerank(self, company_id: object, *args: object, **kwargs: object) -> Any:
        return await _rerank(self, company_id, *args, **kwargs)


# Bind private helpers as methods for API parity with the pre-decomposition class.
CohereReranker._parse = staticmethod(_parse)
CohereReranker._tenant_candidates = staticmethod(_tenant_candidates)
CohereReranker._batch_count = _batch_count
CohereReranker._score = _score
CohereReranker._score_batch = _score_batch
CohereReranker._call_scorer = _call_scorer
CohereReranker._scorer_attempts = _scorer_attempts
CohereReranker._fallback = _fallback
CohereReranker._result = _result


__all__ = ['CohereReranker']
