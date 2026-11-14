"""Port for waiting-line participation around heavy work."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


class WaitingLine(ABC):
    """Interface for wrapping heavy work in a bounded waiting line."""

    @abstractmethod
    async def run(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        """Run work through the waiting line."""
        raise NotImplementedError

    # Backwards-compatible aliases.
    async def execute(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.run(company_id, *args, **kwargs)

    async def submit(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.run(company_id, *args, **kwargs)

    async def participate(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.run(company_id, *args, **kwargs)

    async def wait(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.run(company_id, *args, **kwargs)

    async def enter(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.run(company_id, *args, **kwargs)

    async def acquire(self, company_id: CompanyId, *args: Any, **kwargs: Any) -> Any:
        return await self.run(company_id, *args, **kwargs)


# Backwards-compatible aliases.
WaitingLinePort = WaitingLine
QueueLine = WaitingLine

__all__ = ['QueueLine', 'WaitingLine', 'WaitingLinePort']
