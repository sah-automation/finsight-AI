"""Tests that the metric-repository builder is wired through the composition root."""

from __future__ import annotations

from finsight.adapters.repositories.postgres_metric_repository import PostgresMetricRepository
from finsight.composition import build_container, build_metric_repository


def test_build_metric_repository_selects_the_postgres_adapter() -> None:
    assert isinstance(build_metric_repository(), PostgresMetricRepository)


def test_container_exposes_the_metric_repository_adapter() -> None:
    container = build_container()

    assert isinstance(container.metric_repository, PostgresMetricRepository)
    assert container.metrics is container.metric_repository
    assert container['metric_repository'] is container.metric_repository
    assert container.adapters['metric_repository'] is container.metric_repository


def test_provided_metric_repository_is_preserved() -> None:
    repository = PostgresMetricRepository()

    container = build_container(metric_repository=repository)

    assert container.metric_repository is repository
