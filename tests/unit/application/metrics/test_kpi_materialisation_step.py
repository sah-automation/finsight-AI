from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from finsight.application.metrics.kpi_materialisation_step import KpiMaterialisationStep
from tests.unit.kpi_test_helpers import COMPANY, make_metric


class _MetricRepo:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
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
        self.rows = rows
        self.calls: list[list[Any]] = []

    def compute_all(self, metrics: list[Any]) -> list[dict[str, Any]]:
        self.calls.append(list(metrics))
        return list(self.rows)


@pytest.mark.asyncio
async def test_run_reads_metrics_computes_all_and_upserts() -> None:
    metrics = [make_metric('revenue', '100', metric_id='m1', version='v1')]
    kpi_rows = [{'kpi_code': 'revenue', 'period': '2026-Q3', 'value': '100'}]
    metric_repo = _MetricRepo(metrics)
    kpi_repo = _KpiRepo()
    computation = _Computation(kpi_rows)
    step = KpiMaterialisationStep(
        metric_repository=metric_repo,
        kpi_repository=kpi_repo,
        computation_service=computation,
        delta_tracking=False,  # Disable delta to test basic path
    )
    ctx = SimpleNamespace(company_id=COMPANY, version_id='v1', document_id='d1')

    result = await step.run(ctx)

    assert metric_repo.calls == [(COMPANY, (), {'document_version_id': 'v1'})]
    assert computation.calls == [metrics]
    assert kpi_repo.upserts == [(COMPANY, kpi_rows, {})]
    assert result.kpi_rows == kpi_rows
    assert result.kpi_count == 1


@pytest.mark.asyncio
async def test_run_skips_upsert_when_no_rows() -> None:
    step = KpiMaterialisationStep(
        metric_repository=_MetricRepo([]),
        kpi_repository=_KpiRepo(),
        computation_service=_Computation([]),
        delta_tracking=False,
    )
    ctx = SimpleNamespace(company_id=COMPANY, version_id='v1', document_id='d1')

    result = await step.run(ctx)

    assert result.kpi_rows == []
    assert result.kpi_count == 0
