"""Port for answer caching."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


class AnswerCache(ABC):
    """Interface for storing/clearing cached answers scoped by company."""

    @abstractmethod
    async def get(
        self,
        company_id: CompanyId,
        *,
        key: str | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> object:
        """Fetch a cached answer (or None)."""
        raise NotImplementedError

    @abstractmethod
    async def set(
        self,
        company_id: CompanyId,
        value: object,
        *,
        key: str | None = None,
        ttl_seconds: int | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> None:
        """Store a cached answer."""
        _ = (key, ttl_seconds, role, access_scope, question, document_stamp)
        raise NotImplementedError

    @abstractmethod
    async def clear(
        self,
        company_id: CompanyId,
        **kwargs: object,
    ) -> None:
        """Clear cached answers for a company."""
        raise NotImplementedError

    # Aliases for get.
    async def get_answer(self, company_id: CompanyId, **kwargs: object) -> object:
        return await self.get(company_id, **kwargs)  # type: ignore

    async def fetch(self, company_id: CompanyId, **kwargs: object) -> object:
        return await self.get(company_id, **kwargs)  # type: ignore

    async def get_cached(self, company_id: CompanyId, **kwargs: object) -> object:
        return await self.get(company_id, **kwargs)  # type: ignore

    # Aliases for set.
    async def set_answer(self, company_id: CompanyId, value: object, **kwargs: object) -> None:
        return await self.set(company_id, value, **kwargs)  # type: ignore

    async def put(self, company_id: CompanyId, value: object, **kwargs: object) -> None:
        return await self.set(company_id, value, **kwargs)  # type: ignore

    async def store(self, company_id: CompanyId, value: object, **kwargs: object) -> None:
        return await self.set(company_id, value, **kwargs)  # type: ignore

    # Aliases for clear (company-scoped invalidation).
    async def clear_company(self, company_id: CompanyId, **kwargs: object) -> None:
        return await self.clear(company_id, **kwargs)

    async def clear_for_company(self, company_id: CompanyId, **kwargs: object) -> None:
        return await self.clear(company_id, **kwargs)

    async def invalidate(self, company_id: CompanyId, **kwargs: object) -> None:
        return await self.clear(company_id, **kwargs)

    async def invalidate_company(self, company_id: CompanyId, **kwargs: object) -> None:
        return await self.clear(company_id, **kwargs)

    async def clear_cache(self, company_id: CompanyId, **kwargs: object) -> None:
        return await self.clear(company_id, **kwargs)

    async def delete_for_company(self, company_id: CompanyId, **kwargs: object) -> None:
        return await self.clear(company_id, **kwargs)

    async def delete(self, company_id: CompanyId, key: str | None = None, **kwargs: object) -> bool:
        # Adapter-specific delete; default maps to clear when key is None.
        if key is None:
            await self.clear(company_id, **kwargs)
        return True

    async def exists(self, company_id: CompanyId, **kwargs: object) -> bool:
        return (await self.get(company_id, **kwargs)) is not None  # type: ignore


__all__ = ['AnswerCache']
