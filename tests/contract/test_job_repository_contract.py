"""Contract tests for the JobRepository port."""

from __future__ import annotations

import pytest

from finsight.adapters.repositories.job_repository import (
    JobRepository,
    PostgresJobRepository,
)
from finsight.core.types import CompanyId, JobStatus

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')
JOB = 'job-1'
OTHER_JOB = 'job-2'


@pytest.fixture
def repository() -> JobRepository:
    return JobRepository()


class TestJobRepositoryContract:
    async def test_create_and_get_roundtrip(self, repository: JobRepository) -> None:
        created = await repository.create_job(COMPANY, JOB, status=JobStatus.QUEUED)

        assert created is not None
        assert (
            created.get('job_id') if hasattr(created, 'get') else getattr(created, 'job_id', None)
        ) == JOB

        found = await repository.get_job(COMPANY, JOB)
        assert found is not None

    async def test_get_missing_returns_none(self, repository: JobRepository) -> None:
        assert await repository.get_job(COMPANY, JOB) is None

    async def test_company_isolation(self, repository: JobRepository) -> None:
        await repository.create_job(COMPANY, JOB, status=JobStatus.QUEUED)
        await repository.create_job(OTHER_COMPANY, OTHER_JOB, status=JobStatus.QUEUED)

        assert await repository.get_job(COMPANY, JOB) is not None
        assert await repository.get_job(OTHER_COMPANY, JOB) is None
        assert await repository.get_job(OTHER_COMPANY, OTHER_JOB) is not None

        jobs = await repository.list_jobs(COMPANY)
        assert len(jobs) == 1

    async def test_lifecycle_transition(self, repository: JobRepository) -> None:
        await repository.create_job(COMPANY, JOB, status=JobStatus.QUEUED)

        updated = await repository.update_job(COMPANY, JOB, status=JobStatus.PROCESSING)
        assert updated is not None
        status = (
            updated.get('status') if hasattr(updated, 'get') else getattr(updated, 'status', None)
        )
        assert status == JobStatus.PROCESSING or str(status) == str(JobStatus.PROCESSING)

        await repository.update_job(COMPANY, JOB, status=JobStatus.COMMITTED)
        final = await repository.get_job(COMPANY, JOB)
        final_status = (
            final.get('status') if hasattr(final, 'get') else getattr(final, 'status', None)
        )
        assert final_status == JobStatus.COMMITTED or str(final_status) == str(JobStatus.COMMITTED)

    async def test_update_missing_returns_none(self, repository: JobRepository) -> None:
        assert await repository.update_job(COMPANY, JOB, status=JobStatus.PROCESSING) is None

    async def test_delete_is_tenant_scoped(self, repository: JobRepository) -> None:
        await repository.create_job(COMPANY, JOB, status=JobStatus.QUEUED)

        assert await repository.delete_job(OTHER_COMPANY, JOB) is False
        assert await repository.delete_job(COMPANY, JOB) is True
        assert await repository.get_job(COMPANY, JOB) is None

    async def test_create_is_idempotent(self, repository: JobRepository) -> None:
        await repository.create_job(COMPANY, JOB, status=JobStatus.QUEUED)
        await repository.create_job(COMPANY, JOB, status=JobStatus.COMMITTED)

        jobs = await repository.list_jobs(COMPANY)
        assert len(jobs) == 1
        found = await repository.get_job(COMPANY, JOB)
        status = found.get('status') if hasattr(found, 'get') else getattr(found, 'status', None)
        assert status == JobStatus.COMMITTED or str(status) == str(JobStatus.COMMITTED)


_PostgresJobRepository = PostgresJobRepository
