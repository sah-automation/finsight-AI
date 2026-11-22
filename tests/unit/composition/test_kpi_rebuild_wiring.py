"""The composition root must expose the KPI rebuild job as a use case."""

from __future__ import annotations

from finsight.application.metrics.kpi_rebuild import KpiRebuildJob
from finsight.composition import build_container
from finsight.core.config.loader import load_config


def test_container_exposes_kpi_rebuild_job() -> None:
    container = build_container(config=load_config('test'))

    job = container.use_cases['kpi_rebuild']

    assert isinstance(job, KpiRebuildJob)
    assert job is container.use_cases['kpi_rebuild_job']
    assert job.target_version.startswith('kpi-rules-')
