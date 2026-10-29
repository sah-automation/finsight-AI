"""Port for reading metrics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId


class MetricRepository(ABC):
    """Interface for reading (and mirroring) financial metrics."""

    @abstractmethod
    async def get_metric(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        """Fetch a single metric."""
        raise NotImplementedError

    @abstractmethod
    async def list_metrics(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        """List metrics with optional scope filters."""
        raise NotImplementedError

    # Backwards-compatible aliases.
    async def get_metrics(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.list_metrics(company_id, *args, **kwargs)

    async def find_metrics(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.list_metrics(company_id, *args, **kwargs)

    async def search_metrics(
        self, company_id: CompanyId, *args: object, **kwargs: object
    ) -> object:
        return await self.list_metrics(company_id, *args, **kwargs)

    async def list_metric(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        return await self.list_metrics(company_id, *args, **kwargs)

    async def fetch_metric(self, company_id: CompanyId, *args: object, **kwargs: object) -> object:
        metric = getattr(self, 'get_metric', None)
        if callable(metric):
            return await metric(company_id, *args, **kwargs)
        return await self.list_metrics(company_id, *args, **kwargs)


MetricsRepository = MetricRepository

__all__ = ['MetricRepository', 'MetricsRepository']
