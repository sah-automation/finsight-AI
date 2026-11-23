"""Integration-style test for KPI materialisation delta equivalence (#376).

Uses the KPI repository in-memory seam to compare final stored rows when the
same update is materialised with delta tracking on vs off.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from finsight.adapters.repositories.kpi_repository import KpiRepository
from finsight.application.metrics.kpi_materialisation_step import KpiMaterialisationStep
from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import COMPANY, RULE_VERSION, make_metric


class _MetricRepo:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = list(rows)

    async def list_metrics(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Any]:
        return list(self.rows)


async def _run(delta_tracking: bool) -> list[dict[str, Any]]:
    metrics = [
        make_metric('revenue', '100', metric_id='m1', version='v2', period='2026-Q1'),
        make_metric('operating_expenses', '40', metric_id='m2', version='v2', period='2026-Q1'),
        make_metric('cash_flow', '10', metric_id='m3', version='v2', period='2026-Q1'),
    ]
    kpi_repo = KpiRepository()
    step = KpiMaterialisationStep(
        metric_repository=_MetricRepo(metrics),
        kpi_repository=kpi_repo,
        computation_service=KpiComputationService(RULE_VERSION),
        delta_tracking=delta_tracking,
    )
    ctx = {'company_id': COMPANY, 'version_id': 'v2', 'document_id': 'd1'}
    await step.run(ctx)
    rows = await kpi_repo.get_current(COMPANY)
    return list(rows)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kpi_materialisation_delta_modes_produce_byte_identical_rows() -> None:
    on_rows = await _run(True)
    off_rows = await _run(False)

    assert on_rows
    assert json.dumps(on_rows, sort_keys=True, separators=(',', ':')) == json.dumps(
        off_rows, sort_keys=True, separators=(',', ':')
    )
