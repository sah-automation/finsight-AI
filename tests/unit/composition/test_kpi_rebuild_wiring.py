"""The composition root must expose the KPI rebuild job as a use case."""

from __future__ import annotations

from finsight.application.metrics.kpi_rebuild import KpiRebuildJob
from finsight.composition import build_container
from finsight.composition.container import build_kpi_computation_service
from finsight.core.config.loader import load_config


def test_container_exposes_kpi_rebuild_job() -> None:
    container = build_container(config=load_config('test'))

    job = container.use_cases['kpi_rebuild']

    assert isinstance(job, KpiRebuildJob)
    assert job is container.use_cases['kpi_rebuild_job']
    assert job.target_version.startswith('kpi-rules-')


def test_rebuild_job_and_computation_service_share_the_target_version() -> None:
    config = load_config('test')
    job = build_container(config=config).use_cases['kpi_rebuild']
    service = build_kpi_computation_service(config=config)

    assert service._computation_rule_version == job.target_version
