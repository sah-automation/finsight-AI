"""Port for transactional unit of work."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from finsight.core.types import CompanyId


class UnitOfWork(ABC):
    """Interface for opening and committing a transactional scope."""

    @abstractmethod
    async def begin(
        self,
        company_id: CompanyId | None = None,
        **kwargs: object,
    ) -> UnitOfWork:
        """Begin a transaction and return a transaction handle (defaults to self)."""
        raise NotImplementedError

    async def commit(self, transaction: object = None, **kwargs: object) -> None:
        """Commit a transaction."""
        _ = transaction

    async def rollback(self, transaction: object = None, **kwargs: object) -> None:
        """Roll back a transaction (best-effort)."""
        _ = transaction

    async def close(self, transaction: object = None, **kwargs: object) -> None:
        _ = transaction

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        _ = (exc_type, exc, tb)
        if exc_type is not None:
            await self.rollback(self)
        else:
            await self.commit(self)
        return False

    async def transaction(
        self, company_id: CompanyId | None = None, **kwargs: object
    ) -> UnitOfWork:
        """Return a (re)usable transaction handle for ``async with``."""
        return self

    # Aliases.
    async def begin_transaction(
        self, company_id: CompanyId | None = None, **kwargs: object
    ) -> UnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def start(self, company_id: CompanyId | None = None, **kwargs: object) -> UnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def start_transaction(
        self, company_id: CompanyId | None = None, **kwargs: object
    ) -> UnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def open(self, company_id: CompanyId | None = None, **kwargs: object) -> UnitOfWork:
        return await self.begin(company_id, **kwargs)

    async def enter(self, company_id: CompanyId | None = None, **kwargs: object) -> UnitOfWork:
        return await self.begin(company_id, **kwargs)

    @asynccontextmanager
    async def scope(
        self, company_id: CompanyId | None = None, **kwargs: object
    ) -> AsyncIterator[UnitOfWork]:
        tx = await self.begin(company_id, **kwargs)
        try:
            yield tx
        except Exception:
            await self.rollback(tx)
            raise
        await self.commit(tx)

    async def execute(self, company_id: CompanyId | None = None, **kwargs: object) -> object:
        raise NotImplementedError

    async def run_in_transaction(
        self, company_id: CompanyId | None = None, **kwargs: object
    ) -> object:
        raise NotImplementedError


__all__ = ['UnitOfWork']
