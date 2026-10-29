"""Port for reranking retrieved candidates."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


class Reranker(ABC):
    """Interface for scoring candidates against a question."""

    @abstractmethod
    async def rerank(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        """Rerank candidates and return ordered results."""
        raise NotImplementedError

    # Backwards-compatible aliases.
    async def score(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.rerank(company_id, *args, **kwargs)

    async def rank(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.rerank(company_id, *args, **kwargs)

    async def rerank_candidates(
        self, company_id: CompanyId, *args: object, **kwargs: object
    ) -> object:
        return await self.rerank(company_id, *args, **kwargs)


RerankerPort = Reranker

__all__ = ['Reranker', 'RerankerPort']
