"""Auto-extracted helper for PostgresMetricRepository.upsert_metrics."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_metric_repository_shared import (
    _company,
    _metric_params,
    _row_to_metric,
    _upsert_sql,
)

if TYPE_CHECKING:
    from collections.abc import (
        Sequence,
    )

    from finsight.core.types import CompanyId
    from finsight.domain.entities.metric import Metric


if TYPE_CHECKING:
    from .postgres_metric_repository import PostgresMetricRepository


async def _upsert_metrics(
    self: PostgresMetricRepository,
    company_id: CompanyId,
    metrics: Sequence[Metric],
    **kwargs: object,
) -> list[Metric]:
    company = _company(company_id)
    if self._session is None:
        return self._upsert_memory(company, metrics)
    await self._set_rls_context(company_id)
    saved: list[Metric] = []
    sql = _upsert_sql()
    for metric in metrics:
        params = _metric_params(company, metric)
        result = await self._execute(sql, params)
        saved.append(_row_to_metric(await self._fetchone(result)) or metric)
    return saved
