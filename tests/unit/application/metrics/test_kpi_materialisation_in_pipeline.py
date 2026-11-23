from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from finsight.application.ingest_document.pipeline_step_worker import PipelineStepWorker
from tests.unit.kpi_test_helpers import COMPANY, RULE_VERSION, make_metric


class _MetricRepo:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = list(rows)
        self.calls: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    async def list_metrics(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Any]:
        self.calls.append((company_id, args, dict(kwargs)))
        return list(self.rows)


class _KpiRepo:
    def __init__(self) -> None:
        self.upserts: list[tuple[Any, list[dict[str, Any]], dict[str, Any]]] = []

    async def upsert_batch(
        self, rows: list[dict[str, Any]], *, company_id: Any = None, **kwargs: Any
    ) -> int:
        self.upserts.append((company_id, list(rows), dict(kwargs)))
        return len(rows)


class _Computation:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def compute_all(self, metrics: list[Any]) -> list[dict[str, Any]]:
        return list(self.rows)


@pytest.mark.asyncio
async def test_save_step_materialises_kpis_before_stamp() -> None:
    calls: list[str] = []

    class _DocRepo:
        async def update_document_stamp(
            self, company_id: Any, document_id: Any, stamp: Any, **kwargs: Any
        ) -> Any:
            calls.append('stamp')
            return stamp

    metric_repo = _MetricRepo([make_metric('revenue', '100', metric_id='m1', version='v1')])
    kpi_repo = _KpiRepo()

    async def _upsert(rows: list[dict[str, Any]], *, company_id: Any = None, **kwargs: Any) -> int:
        calls.append('kpi_upsert')
        return await _KpiRepo.upsert_batch(kpi_repo, rows, company_id=company_id, **kwargs)

    kpi_repo.upsert_batch = _upsert  # type: ignore[method-assign]

    worker = PipelineStepWorker(
        step_name='save',
        metric_repository=metric_repo,
        kpi_repository=kpi_repo,
        kpi_computation_service=_Computation(
            [{'kpi_code': 'revenue', 'period': '2026-Q3', 'value': '100'}]
        ),
        document_repository=_DocRepo(),
        kpi_computation_rule_version=RULE_VERSION,
    )

    await worker.handle(
        company_id=COMPANY,
        version_id='v1',
        document_id='d1',
        key='company/doc/v1.pdf',
        step='save',
        version=SimpleNamespace(state='processing'),
    )

    assert 'kpi_upsert' in calls
    assert 'stamp' in calls
    assert calls.index('kpi_upsert') < calls.index('stamp')
