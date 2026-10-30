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

    async def test_reconcile_applies_the_newer_aurora_commit(
        self, progress: JobProgressPort
    ) -> None:
        await progress.write_progress(
            COMPANY,
            'job-order',
            status='processing',
            progress=40,
            revision=1,
        )

        await progress.reconcile_progress(
            COMPANY,
            'job-order',
            status='committed',
            progress=100,
            revision=2,
            aurora_committed_at='2026-10-30T10:00:02+00:00',
        )

        record = await progress.read_progress(COMPANY, 'job-order')
        assert record is not None
        assert record.get('status') == 'committed'
        assert record.get('progress') == 100
        assert record.get('revision') == 2
        assert record.get('source') == 'aurora'

    async def test_reconcile_rejects_an_out_of_order_update(
        self, progress: JobProgressPort
    ) -> None:
        await progress.reconcile_progress(
            COMPANY,
            'job-stale',
            status='committed',
            progress=100,
            revision=3,
            aurora_committed_at='2026-10-30T10:00:03+00:00',
        )

        await progress.reconcile_progress(
            COMPANY,
            'job-stale',
            status='processing',
            progress=20,
            revision=2,
            aurora_committed_at='2026-10-30T10:00:02+00:00',
        )

        record = await progress.read_progress(COMPANY, 'job-stale')
        assert record is not None
        assert record.get('status') == 'committed'
        assert record.get('progress') == 100
        assert record.get('revision') == 3

    async def test_reconcile_ignores_a_duplicate_update(self, progress: JobProgressPort) -> None:
        await progress.reconcile_progress(
            COMPANY,
            'job-duplicate',
            status='committed',
            progress=100,
            revision=4,
            aurora_committed_at='2026-10-30T10:00:04+00:00',
        )
        original = await progress.read_progress(COMPANY, 'job-duplicate')
        assert original is not None
        original_updated_at = original.get('updated_at')

        await progress.reconcile_progress(
            COMPANY,
            'job-duplicate',
            status='committed',
            progress=100,
            revision=4,
            aurora_committed_at='2026-10-30T10:00:04+00:00',
        )

        record = await progress.read_progress(COMPANY, 'job-duplicate')
        assert record is not None
        assert record.get('status') == 'committed'
        assert record.get('progress') == 100
        assert record.get('updated_at') == original_updated_at

    async def test_reconcile_rejects_a_conflicting_duplicate(
        self, progress: JobProgressPort
    ) -> None:
        await progress.reconcile_progress(
            COMPANY,
            'job-conflict',
            status='committed',
            progress=100,
            revision=5,
            aurora_committed_at='2026-10-30T10:00:05+00:00',
        )

        await progress.reconcile_progress(
            COMPANY,
            'job-conflict',
            status='failed',
            progress=0,
            revision=5,
            aurora_committed_at='2026-10-30T10:00:05+00:00',
        )

        record = await progress.read_progress(COMPANY, 'job-conflict')
        assert record is not None
        assert record.get('status') == 'committed'
        assert record.get('progress') == 100

    async def test_reconcile_without_aurora_ordering_fails_loudly(
        self, progress: JobProgressPort
    ) -> None:
        with pytest.raises(ValueError, match='revision or aurora_committed_at'):
            await progress.reconcile_progress(COMPANY, 'job-unordered', status='committed')

    async def test_reconcile_orders_by_commit_time_without_a_revision(
        self, progress: JobProgressPort
    ) -> None:
        await progress.reconcile_progress(
            COMPANY,
            'job-clock',
            status='committed',
            progress=100,
            aurora_committed_at='2026-10-30T10:00:05+00:00',
        )

        await progress.reconcile_progress(
            COMPANY,
            'job-clock',
            status='processing',
            progress=50,
            aurora_committed_at='2026-10-30T10:00:04+00:00',
        )

        record = await progress.read_progress(COMPANY, 'job-clock')
        assert record is not None
        assert record.get('status') == 'committed'
        assert record.get('progress') == 100

    async def test_reconcile_rejects_mixed_ordering_tokens(self, progress: JobProgressPort) -> None:
        await progress.reconcile_progress(
            COMPANY,
            'job-mixed',
            status='committed',
            progress=100,
            revision=7,
        )

        await progress.reconcile_progress(
            COMPANY,
            'job-mixed',
            status='processing',
            progress=10,
            aurora_committed_at='2026-10-30T10:00:10+00:00',
        )

        record = await progress.read_progress(COMPANY, 'job-mixed')
        assert record is not None
        assert record.get('status') == 'committed'
        assert record.get('progress') == 100
        assert record.get('revision') == 7
