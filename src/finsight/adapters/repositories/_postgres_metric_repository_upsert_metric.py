"""Auto-extracted helper for PostgresMetricRepository.upsert_metric."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.metric import Metric

# Host module-level definitions (injected at runtime of this helper)


if TYPE_CHECKING:
    from .postgres_metric_repository import PostgresMetricRepository


async def _upsert_metric(
    self: PostgresMetricRepository,
    company_id: CompanyId,
    metric: Metric,
    **kwargs: object,
) -> Metric:
    saved = await self.upsert_metrics(company_id, [metric], **kwargs)
    return saved[0] if saved else metric
