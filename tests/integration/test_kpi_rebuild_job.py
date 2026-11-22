"""Integration coverage for the KPI rebuild job (issue #377).

Runs the real KPI computation service, KPI repository, rebuild-state store and
waiting line together through their in-memory seams. It checks that a rerun
produces identical rows, that a target version is gated until completion, and
that rebuild priorities stay below live questions and uploads.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from finsight.adapters.repositories.kpi_rebuild_state_repository import (
    KpiRebuildStateRepository,
)
from finsight.adapters.repositories.kpi_repository import KpiRepository
from finsight.adapters.repositories.postgres_metric_repository import PostgresMetricRepository
from finsight.adapters.waiting_line.passthrough_waiting_line import PassthroughWaitingLine
from finsight.application.metrics.kpi_rebuild import KpiRebuildJob
from finsight.core.config.loader import load_config
from finsight.core.config.models.kpi_config import KpiConfig
from finsight.core.work_priority import assert_rebuild_priority_ordering, priority_rank
from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import COMPANY, make_metric

pytestmark = pytest.mark.integration

SECOND_COMPANY = type(COMPANY)('7e1a0000-0000-4000-8000-000000000002')
VERSION = 'rules-v2'


class _RecordingLine:
    """Wrap the real passthrough line to observe the submitted priority."""

    def __init__(self) -> None:
        self.delegate = PassthroughWaitingLine()
        self.priorities: list[str | None] = []

    async def run(self, company_id: Any, work: Any, **kwargs: Any) -> Any:
        self.priorities.append(kwargs.get('priority'))
        return await self.delegate.run(company_id, work, **kwargs)


class _FailingMetricRepository:
    def __init__(self, delegate: PostgresMetricRepository, failed: Any) -> None:
        self.delegate = delegate
        self.failed = str(failed)

    async def list_metrics(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if str(company_id) == self.failed:
            raise RuntimeError(f'metrics unavailable for {company_id}')
        return await self.delegate.list_metrics(company_id, *args, **kwargs)


def _config(priority: str = 'rebuilds') -> Any:
    base = load_config('test')
    kpi = base.kpi.model_copy(update={'rebuild_priority': priority, 'rebuild_batch_size': 2})
    return base.model_copy(update={'kpi': kpi})


async def _metrics() -> PostgresMetricRepository:
    repo = PostgresMetricRepository()
    for company in (COMPANY, SECOND_COMPANY):
        metric = make_metric(
            'revenue',
            Decimal('1000'),
            metric_id=f'{company}-revenue',
            version='doc-v1',
        )
        metric.company_id = company
        await repo.upsert_metric(company, metric)
    return repo


def _job(
    *,
    config: Any,
    state: KpiRebuildStateRepository,
    metrics: Any,
    kpi_repo: KpiRepository,
    line: _RecordingLine,
    version: str = VERSION,
) -> KpiRebuildJob:
    return KpiRebuildJob(
        config=config,
        metric_repository=metrics,
        kpi_repository=kpi_repo,
        computation_service=KpiComputationService(version),
        rebuild_state=state,
        waiting_line=line,
        target_version=version,
    )


async def test_rerun_produces_identical_rows_at_configured_priority() -> None:
    state, kpi_repo, line = KpiRebuildStateRepository(), KpiRepository(), _RecordingLine()
    metrics = await _metrics()
    job = _job(
        config=_config('background'),
        state=state,
        metrics=metrics,
        kpi_repo=kpi_repo,
        line=line,
    )

    first = await job.run([COMPANY, SECOND_COMPANY])
    rows_after_first = [
        await kpi_repo.get_current(company) for company in (COMPANY, SECOND_COMPANY)
    ]
    second = await job.run([COMPANY, SECOND_COMPANY])
    rows_after_second = [
        await kpi_repo.get_current(company) for company in (COMPANY, SECOND_COMPANY)
    ]

    assert first['status'] == second['status'] == 'complete'
    assert rows_after_first == rows_after_second
    assert all(rows for rows in rows_after_first)
    assert line.priorities == ['background'] * 4
    assert [len(batch) for batch in first['batches']] == [2]


async def test_new_version_is_gated_until_rebuild_completes() -> None:
    state, kpi_repo = KpiRebuildStateRepository(), KpiRepository()
    metrics = await _metrics()
    failing = _FailingMetricRepository(metrics, SECOND_COMPANY)
    blocked = _job(
        config=_config(),
        state=state,
        metrics=failing,
        kpi_repo=kpi_repo,
        line=_RecordingLine(),
        version='rules-v3',
    )

    first = await blocked.run([COMPANY, SECOND_COMPANY])

    assert first['status'] == 'incomplete'
    assert await state.get('rules-v3') == 'running'
    assert await blocked.is_active() is False
    assert await state.incomplete_versions() == ['rules-v3']

    working = _job(
        config=_config(),
        state=state,
        metrics=metrics,
        kpi_repo=kpi_repo,
        line=_RecordingLine(),
        version='rules-v3',
    )
    second = await working.run([COMPANY, SECOND_COMPANY])

    assert second['status'] == 'complete'
    assert await working.is_active() is True
    assert await state.incomplete_versions() == []


def test_rebuild_ranks_follow_the_startup_ordering_assertion() -> None:
    assert_rebuild_priority_ordering()
    live_rank = max(priority_rank(name) for name in ('question', 'search', 'model'))
    upload_rank = priority_rank('upload')

    assert priority_rank('rebuilds') > max(live_rank, upload_rank)
    assert priority_rank('background') > max(live_rank, upload_rank)

    base = load_config('test')
    with pytest.raises(ValidationError):
        KpiConfig.model_validate({**base.kpi.model_dump(), 'rebuild_priority': 'upload'})
