"""Port for job status persistence (Aurora is the source of truth)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finsight.core.types import CompanyId, JobStatus


class JobRepository(ABC):
    """Interface for creating and updating ingestion job records."""

    @abstractmethod
    async def create_job(
        self,
        company_id: CompanyId,
        job_id: object,
        *,
        status: JobStatus | str | None = None,
        **kwargs: object,
    ) -> object:
        """Create a job record."""
        raise NotImplementedError

    @abstractmethod
    async def get_job(
        self,
        company_id: CompanyId,
        job_id: object,
        **kwargs: object,
    ) -> object:
        """Fetch a job record by id."""
        raise NotImplementedError

    @abstractmethod
    async def update_job(
        self,
        company_id: CompanyId,
        job_id: object,
        *,
        status: JobStatus | str | None = None,
        **kwargs: object,
    ) -> object:
        """Update a job record's fields."""
        raise NotImplementedError

    @abstractmethod
    async def list_jobs(
        self,
        company_id: CompanyId,
        **kwargs: object,
    ) -> list[object]:
        """List job records for a company."""
        raise NotImplementedError

    @abstractmethod
    async def delete_job(
        self,
        company_id: CompanyId,
        job_id: object,
        **kwargs: object,
    ) -> bool:
        """Delete a job record. Returns True when deleted."""
        raise NotImplementedError

    # Aliases.
    async def create(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.create_job(company_id, job_id, **kwargs)  # type: ignore

    async def insert(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.create_job(company_id, job_id, **kwargs)  # type: ignore

    async def add_job(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.create_job(company_id, job_id, **kwargs)  # type: ignore

    async def upsert_job(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.create_job(company_id, job_id, **kwargs)  # type: ignore

    async def upsert(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.create_job(company_id, job_id, **kwargs)  # type: ignore

    async def get(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.get_job(company_id, job_id, **kwargs)

    async def fetch(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.get_job(company_id, job_id, **kwargs)

    async def fetch_job(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.get_job(company_id, job_id, **kwargs)

    async def find(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.get_job(company_id, job_id, **kwargs)

    async def find_job(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.get_job(company_id, job_id, **kwargs)

    async def list(self, company_id: CompanyId, **kwargs: object) -> list[object]:
        return await self.list_jobs(company_id, **kwargs)

    async def update_job_status(
        self, company_id: CompanyId, job_id: object, **kwargs: object
    ) -> object:
        return await self.update_job(company_id, job_id, **kwargs)  # type: ignore

    async def update_status(
        self, company_id: CompanyId, job_id: object, **kwargs: object
    ) -> object:
        return await self.update_job(company_id, job_id, **kwargs)  # type: ignore

    async def set_status(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.update_job(company_id, job_id, **kwargs)  # type: ignore

    async def mark_status(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.update_job(company_id, job_id, **kwargs)  # type: ignore

    async def mark_job(self, company_id: CompanyId, job_id: object, **kwargs: object) -> object:
        return await self.update_job(company_id, job_id, **kwargs)  # type: ignore

    async def delete(self, company_id: CompanyId, job_id: object, **kwargs: object) -> bool:
        return await self.delete_job(company_id, job_id, **kwargs)

    async def remove_job(self, company_id: CompanyId, job_id: object, **kwargs: object) -> bool:
        return await self.delete_job(company_id, job_id, **kwargs)


__all__ = ['JobRepository']
