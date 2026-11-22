from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.application.metrics.kpi_materialisation_step import KpiMaterialisationStep
from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import COMPANY, RULE_VERSION, make_metric


class _MetricRepo:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = list(rows)

    async def list_metrics(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Any]:
        return list(self.rows)


class _KpiRepo:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def upsert_batch(
        self, rows: list[dict[str, Any]], *, company_id: Any = None, **kwargs: Any
    ) -> int:
        self.rows.extend(list(rows))
        return len(rows)


@pytest.mark.asyncio
@pytest.mark.parametrize('delta_tracking', [True, False])
async def test_delta_modes_produce_identical_rows(delta_tracking: bool) -> None:
    metrics = [
        make_metric('revenue', '100', metric_id='m1', version='v2', period='2026-Q1'),
        make_metric('operating_expenses', '40', metric_id='m2', version='v2', period='2026-Q1'),
    ]
    kpi_repo = _KpiRepo()
    step = KpiMaterialisationStep(
        metric_repository=_MetricRepo(metrics),
        kpi_repository=kpi_repo,
        computation_service=KpiComputationService(RULE_VERSION),
        delta_tracking=delta_tracking,
    )
    ctx = SimpleNamespace(company_id=COMPANY, version_id='v2', document_id='d1')

    await step.run(ctx)

    assert kpi_repo.rows


@pytest.mark.asyncio
async def test_delta_on_and_off_rows_are_byte_identical() -> None:
    metrics = [
        make_metric('revenue', '100', metric_id='m1', version='v2', period='2026-Q1'),
        make_metric('operating_expenses', '40', metric_id='m2', version='v2', period='2026-Q1'),
        make_metric('cash_flow', '10', metric_id='m3', version='v2', period='2026-Q1'),
    ]

    async def run(delta_tracking: bool) -> list[dict[str, Any]]:
        repo = _KpiRepo()
        step = KpiMaterialisationStep(
            metric_repository=_MetricRepo(metrics),
            kpi_repository=repo,
            computation_service=KpiComputationService(RULE_VERSION),
            delta_tracking=delta_tracking,
        )
        ctx = SimpleNamespace(company_id=COMPANY, version_id='v2', document_id='d1')
        await step.run(ctx)
        return repo.rows

    on_rows = await run(True)
    off_rows = await run(False)
    assert json.dumps(on_rows, sort_keys=True, separators=(',', ':')) == json.dumps(
        off_rows, sort_keys=True, separators=(',', ':')
    )
