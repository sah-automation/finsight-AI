"""Unit tests for the rolling KPI rebuild job (issue #377)."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.application.metrics.kpi_rebuild import KpiRebuildJob, kpi_rule_version

pytestmark = pytest.mark.unit

VERSION = 'rules-v2'


class _State:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.events: list[tuple[str, str]] = []

    async def get(self, version: str) -> str | None:
        return self.values.get(version)

    async def is_complete(self, version: str) -> bool:
        return self.values.get(version) == 'complete'

    async def ensure_pending(self, version: str) -> None:
        self.events.append(('pending', version))
        self.values.setdefault(version, 'pending')

    async def mark_running(self, version: str) -> None:
        self.events.append(('running', version))
        if self.values.get(version) in (None, 'pending'):
            self.values[version] = 'running'

    async def mark_complete(self, version: str) -> None:
        self.events.append(('complete', version))
        self.values[version] = 'complete'

    async def incomplete_versions(self) -> list[str]:
        return sorted(v for v, s in self.values.items() if s != 'complete')


class _Line:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def run(self, company_id: Any, work: Any, **kwargs: Any) -> Any:
        self.calls.append((str(company_id), kwargs.get('priority')))
        return await work()


class _Metrics:
    def __init__(self) -> None:
        self.fail_once: set[str] = set()
        self.calls: list[str] = []

    async def list_metrics(self, company_id: Any, *args: Any, **kwargs: Any) -> list[str]:
        tenant = str(company_id)
        self.calls.append(tenant)
        if tenant in self.fail_once:
            self.fail_once.remove(tenant)
            raise RuntimeError(f'metrics unavailable for {tenant}')
        return [tenant]


class _Compute:
    def compute_all(self, metrics: list[str]) -> list[dict[str, Any]]:
        tenant = metrics[0]
        return [
            {
                'company_id': tenant,
                'kpi_code': 'revenue',
                'period': '2025-Q1',
                'document_version_id': f'doc-{tenant}',
                'chart_period': '2025-Q1',
                'value': '100',
                'computation_rule_version': VERSION,
            }
        ]


class _Tracing:
    def __init__(self) -> None:
        self.spans: list[tuple[str, str, dict[str, Any]]] = []

    async def start_span(self, company_id: Any, operation: str, **kwargs: Any) -> None:
        self.spans.append((str(company_id), operation, dict(kwargs.get('attributes') or {})))


class _KpiRepo:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list[dict[str, Any]]]] = []
        self.deletes: list[Any] = []

    async def upsert_batch(
        self, rows: list[dict[str, Any]], *, company_id: Any = None, **kwargs: Any
    ) -> int:
        self.upserts.append((str(company_id), [dict(row) for row in rows]))
        return len(rows)

    async def delete(self, *args: Any, **kwargs: Any) -> None:
        self.deletes.append((args, kwargs))
        raise AssertionError('rebuild must never delete KPI rows')


def _job(
    *,
    state: _State | None = None,
    line: _Line | None = None,
    metrics: _Metrics | None = None,
    kpi_repo: _KpiRepo | None = None,
    batch_size: int = 2,
    priority: str = 'rebuilds',
    tracing: _Tracing | None = None,
    company_repository: Any = None,
) -> KpiRebuildJob:
    return KpiRebuildJob(
        config=SimpleNamespace(rebuild_batch_size=batch_size, rebuild_priority=priority),
        metric_repository=metrics or _Metrics(),
        kpi_repository=kpi_repo or _KpiRepo(),
        computation_service=_Compute(),
        rebuild_state=state or _State(),
        waiting_line=line or _Line(),
        company_repository=company_repository,
        tracing=tracing,
        target_version=VERSION,
    )


async def test_first_run_batches_companies_and_completes() -> None:
    state, line, kpi_repo = _State(), _Line(), _KpiRepo()
    job = _job(state=state, line=line, kpi_repo=kpi_repo)

    result = await job.run([f'c{i}' for i in range(5)])

    assert result['status'] == 'complete'
    assert result['version'] == VERSION
    assert state.events == [
        ('pending', VERSION),
        ('running', VERSION),
        ('complete', VERSION),
    ]
    assert [len(batch) for batch in result['batches']] == [2, 2, 1]
    assert [priority for _, priority in line.calls] == ['rebuilds'] * 5
    assert [tenant for tenant, _ in kpi_repo.upserts] == [f'c{i}' for i in range(5)]
    assert kpi_repo.deletes == []


async def test_failed_company_is_retried_and_completes_only_after_success() -> None:
    state, metrics, kpi_repo = _State(), _Metrics(), _KpiRepo()
    metrics.fail_once.add('c1')
    job = _job(state=state, metrics=metrics, kpi_repo=kpi_repo)
    tenants = ['c0', 'c1', 'c2']

    first = await job.run(tenants)
    assert first['status'] == 'incomplete'
    assert first['failed'] == ['c1']
    assert await state.is_complete(VERSION) is False

    second = await job.run(tenants)
    assert second['status'] == 'complete'
    assert second['failed'] == []
    assert await state.is_complete(VERSION) is True
    assert [tenant for tenant, _ in kpi_repo.upserts].count('c1') == 1
    assert kpi_repo.deletes == []


async def test_rerun_is_idempotent() -> None:
    state, kpi_repo = _State(), _KpiRepo()
    job = _job(state=state, kpi_repo=kpi_repo)

    first = await job.run(['c0'])
    second = await job.run(['c0'])

    expected_rows = [
        {
            'company_id': 'c0',
            'kpi_code': 'revenue',
            'period': '2025-Q1',
            'document_version_id': 'doc-c0',
            'chart_period': '2025-Q1',
            'value': '100',
            'computation_rule_version': VERSION,
        }
    ]
    assert first['status'] == second['status'] == 'complete'
    assert [rows for _, rows in kpi_repo.upserts] == [expected_rows, expected_rows]


async def test_invalid_priority_or_batch_size_is_rejected() -> None:
    with pytest.raises(ValueError, match='rebuild_priority'):
        KpiRebuildJob(
            config=SimpleNamespace(rebuild_batch_size=2, rebuild_priority='upload'),
            metric_repository=_Metrics(),
            kpi_repository=_KpiRepo(),
            computation_service=_Compute(),
            rebuild_state=_State(),
            waiting_line=_Line(),
            target_version=VERSION,
        )
    with pytest.raises(ValueError, match='rebuild_batch_size'):
        _job(batch_size=0)


def test_target_version_is_shared_with_kpi_computation() -> None:
    section = SimpleNamespace(
        codes=['revenue'],
        estimation_methods={'revenue': 'quarterly_spread_equal'},
        rebuild_batch_size=10,
        rebuild_priority='rebuilds',
    )
    assert kpi_rule_version(SimpleNamespace(kpi=section)).startswith('kpi-rules-')

    explicit = SimpleNamespace(
        kpi=SimpleNamespace(
            computation_rule_version='rules-v9',
            rebuild_batch_size=10,
            rebuild_priority='rebuilds',
        )
    )
    assert kpi_rule_version(explicit) == 'rules-v9'
    assert _job(target_version=kpi_rule_version(explicit)).target_version == 'rules-v9'


async def test_company_resolution_failure_leaves_version_pending() -> None:
    state = _State()

    class _BrokenCompanies:
        def list_companies(self) -> list[str]:
            raise RuntimeError('company directory unavailable')

    job = KpiRebuildJob(
        config=SimpleNamespace(rebuild_batch_size=2, rebuild_priority='rebuilds'),
        metric_repository=_Metrics(),
        kpi_repository=_KpiRepo(),
        computation_service=_Compute(),
        rebuild_state=state,
        waiting_line=_Line(),
        company_repository=_BrokenCompanies(),
        target_version=VERSION,
    )

    with pytest.raises(RuntimeError, match='company directory unavailable'):
        await job.run()

    assert state.values == {VERSION: 'pending'}
    assert state.events == [('pending', VERSION)]


async def test_each_company_emits_rebuild_span_with_batch_and_version() -> None:
    tracing = _Tracing()

    await _job(tracing=tracing).run(['c0', 'c1', 'c2'])

    assert [operation for _, operation, _ in tracing.spans] == ['kpi.rebuild.company'] * 3
    assert [attributes['batch_id'] for _, _, attributes in tracing.spans] == [
        f'{VERSION}:0',
        f'{VERSION}:0',
        f'{VERSION}:1',
    ]
    first_attributes = tracing.spans[0][2]
    assert first_attributes['target_rule_version'] == VERSION
    assert first_attributes['outcome'] == 'success'
    assert first_attributes['duration_ms'] >= 0


async def test_failed_company_is_logged_with_trace_id(caplog: pytest.LogCaptureFixture) -> None:
    metrics = _Metrics()
    metrics.fail_once.add('c0')
    caplog.set_level(logging.WARNING)

    result = await _job(metrics=metrics).run(['c0'])

    assert result['failed'] == ['c0']
    assert any('kpi rebuild failed' in record.getMessage() for record in caplog.records)
    assert any('trace_id=' in record.getMessage() for record in caplog.records)
