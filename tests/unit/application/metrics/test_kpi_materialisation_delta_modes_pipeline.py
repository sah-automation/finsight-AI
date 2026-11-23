from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from finsight.application.ingest_document.pipeline_step_worker import PipelineStepWorker
from finsight.domain.services.kpi_computation_service import KpiComputationService
from tests.unit.kpi_test_helpers import COMPANY, RULE_VERSION, make_metric


class _MetricRepo:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = list(rows)

    async def list_metrics(self, company_id: Any, *args: Any, **kwargs: Any) -> list[Any]:
        return list(self.rows)


class _KpiRepo:
    def __init__(self) -> None:
        self.upserts: list[list[dict[str, Any]]] = []

    async def upsert_batch(
        self, rows: list[dict[str, Any]], *, company_id: Any = None, **kwargs: Any
    ) -> int:
        self.upserts.append(list(rows))
        return len(rows)


class _DocRepo:
    async def update_document_stamp(
        self, company_id: Any, document_id: Any, stamp: Any, **kwargs: Any
    ) -> Any:
        return stamp


async def _run(delta_tracking: bool) -> list[dict[str, Any]]:
    metrics = [
        make_metric('revenue', '100', metric_id='m1', version='v2', period='2026-Q1'),
        make_metric('operating_expenses', '40', metric_id='m2', version='v2', period='2026-Q1'),
    ]
    kpi_repo = _KpiRepo()
    worker = PipelineStepWorker(
        step_name='save',
        metric_repository=_MetricRepo(metrics),
        kpi_repository=kpi_repo,
        kpi_computation_service=KpiComputationService(RULE_VERSION),
        document_repository=_DocRepo(),
        delta_tracking=delta_tracking,
        kpi_computation_rule_version=RULE_VERSION,
    )
    await worker.handle(
        company_id=COMPANY,
        version_id='v2',
        document_id='d1',
        key='company/doc/v2.pdf',
        step='save',
        version=SimpleNamespace(state='processing'),
    )
    assert kpi_repo.upserts
    return kpi_repo.upserts[-1]


@pytest.mark.asyncio
async def test_pipeline_save_delta_modes_produce_byte_identical_kpi_rows() -> None:
    on_rows = await _run(True)
    off_rows = await _run(False)
    assert json.dumps(on_rows, sort_keys=True, separators=(',', ':')) == json.dumps(
        off_rows, sort_keys=True, separators=(',', ':')
    )
