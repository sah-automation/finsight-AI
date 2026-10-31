"""Auto-extracted helper for PostgresMetricRepository._list_memory."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_metric_repository_shared import (
    _Filters,
    _period_sort_key,
)

if TYPE_CHECKING:
    from finsight.domain.entities.metric import Metric


if TYPE_CHECKING:
    from .postgres_metric_repository import PostgresMetricRepository


def _list_memory(self: PostgresMetricRepository, company: str, filters: _Filters) -> list[Metric]:
    metrics = list(self._memory.get(company, {}).values())
    selected = [metric for metric in metrics if filters.matches(metric)]
    selected.sort(
        key=lambda metric: (_period_sort_key(metric), str(metric.name), str(metric.metric_id))
    )
    if filters.limit is not None:
        return selected[: filters.limit]
    return selected
