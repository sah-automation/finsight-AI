"""Auto-extracted helper for PostgresMetricRepository._upsert_memory."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )

    from finsight.domain.entities.metric import Metric

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_metric_repository import PostgresMetricRepository


def _upsert_memory(
    self: PostgresMetricRepository, company: str, metrics: Sequence[Metric]
) -> list[Metric]:
    store = self._memory.setdefault(company, {})
    saved: list[Metric] = []
    for metric in metrics:
        if str(metric.company_id) != company:
            raise ValueError('metric company_id must match the repository tenant')
        store[str(metric.metric_id)] = metric
        saved.append(metric)
    return saved
