"""Port for company (tenant) data access."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.company import Company


class CompanyRepository(ABC):
    """Interface for storing and retrieving company records."""

    @abstractmethod
    async def create_company(
        self,
        company_id: CompanyId,
        name: str,
        slug: str,
    ) -> Company:
        """Create a company record. Returns the created company."""
        raise NotImplementedError

    @abstractmethod
    async def get_company(
        self,
        company_id: CompanyId,
    ) -> Company | None:
        """Get a company by its company_id."""
        raise NotImplementedError

    @abstractmethod
    async def get_company_by_slug(
        self,
        company_id: CompanyId,
        slug: str,
    ) -> Company | None:
        """Get a company by a slug scoped to the tenant."""
        raise NotImplementedError

    @abstractmethod
    async def update_company(
        self,
        company_id: CompanyId,
        name: str | None = None,
        slug: str | None = None,
    ) -> Company | None:
        """Update company fields. Returns the updated company (or None)."""
        raise NotImplementedError

    @abstractmethod
    async def delete_company(
        self,
        company_id: CompanyId,
    ) -> bool:
        """Delete a company record. Returns True if deleted."""
        raise NotImplementedError

    @abstractmethod
    async def list_companies(
        self,
        company_id: CompanyId,
    ) -> list[Company]:
        """List companies visible to the given tenant context."""
        raise NotImplementedError
