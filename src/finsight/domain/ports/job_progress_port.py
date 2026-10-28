"""Port for job progress view (DynamoDB is rebuildable)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JobProgressPort(ABC):
    """Interface for writing/reading rebuildable job progress."""

    @abstractmethod
    async def write_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def read_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def list_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def delete_progress(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    # aliases
    async def write(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.write_progress(company_id, *args, **kwargs)

    async def put(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.write_progress(company_id, *args, **kwargs)

    async def upsert(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.write_progress(company_id, *args, **kwargs)

    async def save(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.write_progress(company_id, *args, **kwargs)

    async def get(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.read_progress(company_id, *args, **kwargs)

    async def fetch(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.read_progress(company_id, *args, **kwargs)

    async def read(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.read_progress(company_id, *args, **kwargs)

    async def list(self, company_id: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.list_progress(company_id, *args, **kwargs)


__all__ = ['JobProgressPort']
