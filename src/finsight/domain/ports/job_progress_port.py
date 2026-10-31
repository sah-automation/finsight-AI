"""Port for job progress view (DynamoDB is rebuildable)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


class JobProgressPort(ABC):
    """Interface for writing/reading rebuildable job progress."""

    @abstractmethod
    async def write_progress(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> object:
        raise NotImplementedError

    @abstractmethod
    async def read_progress(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def list_progress(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def reconcile_progress(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> object:
        """Apply one Aurora-committed state using a strict ordering token."""
        raise NotImplementedError

    @abstractmethod
    async def delete_progress(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> object:
        raise NotImplementedError

    # aliases
    async def write(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.write_progress(company_id, *args, **kwargs)

    async def put(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.write_progress(company_id, *args, **kwargs)

    async def upsert(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.write_progress(company_id, *args, **kwargs)

    async def save(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.write_progress(company_id, *args, **kwargs)

    async def get(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.read_progress(company_id, *args, **kwargs)

    async def fetch(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.read_progress(company_id, *args, **kwargs)

    async def read(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.read_progress(company_id, *args, **kwargs)

    async def list(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.list_progress(company_id, *args, **kwargs)


__all__ = ['JobProgressPort']
