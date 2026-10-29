"""Contract tests for the JobProgressPort port."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.cache.job_progress import JobProgress
from finsight.core.types import CompanyId

if TYPE_CHECKING:
    from finsight.domain.ports.job_progress_port import JobProgressPort

pytestmark = pytest.mark.contract

COMPANY = CompanyId('company-a')
OTHER_COMPANY = CompanyId('company-b')


@pytest.fixture
def progress() -> JobProgressPort:
    instance = JobProgress(table_name=f'job-progress-contract-{id(object())}')
    instance.table = None
    return instance


class TestJobProgressPortContract:
    async def test_round_trip_is_tenant_scoped(self, progress: JobProgressPort) -> None:
        await progress.write_progress(COMPANY, 'job-1', status='queued', progress=10)

        record = await progress.read_progress(COMPANY, 'job-1')
        assert record is not None
        assert record.get('company_id') == str(COMPANY)
        assert record.get('job_id') == 'job-1'
        assert record.get('status') == 'queued'
        assert await progress.read_progress(OTHER_COMPANY, 'job-1') is None

    async def test_list_filters_by_company(self, progress: JobProgressPort) -> None:
        await progress.write_progress(COMPANY, 'job-a', status='queued')
        await progress.write_progress(OTHER_COMPANY, 'job-b', status='queued')

        company_jobs = await progress.list_progress(COMPANY)
        other_jobs = await progress.list_progress(OTHER_COMPANY)

        assert {job.get('job_id') for job in company_jobs} == {'job-a'}
        assert {job.get('job_id') for job in other_jobs} == {'job-b'}

    async def test_delete_removes_one_entry(self, progress: JobProgressPort) -> None:
        await progress.write_progress(COMPANY, 'job-delete', status='queued')

        assert await progress.delete_progress(COMPANY, 'job-delete') is True
        assert await progress.read_progress(COMPANY, 'job-delete') is None
