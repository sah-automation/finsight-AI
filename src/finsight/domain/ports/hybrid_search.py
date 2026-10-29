"""Port for hybrid (vector + keyword) search."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


class HybridSearch(ABC):
    """Interface for hybrid retrieval behind one uniform port."""

    @abstractmethod
    async def search(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        """Search candidates for a company."""
        raise NotImplementedError

    # Backwards-compatible aliases.
    async def hybrid_search(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.search(company_id, *args, **kwargs)

    async def retrieve(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.search(company_id, *args, **kwargs)

    async def find(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.search(company_id, *args, **kwargs)


HybridSearchPort = HybridSearch
VectorSearch = HybridSearch

__all__ = ['HybridSearch', 'HybridSearchPort', 'VectorSearch']
