"""Auto-extracted helper for PostgresMetricRepository.get_metric."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
)

# Host module-level definitions (injected at runtime of this helper)
from ._postgres_metric_repository_shared import (
    _RETURNING,
    _TABLE,
    _company,
    _first,
    _row_to_metric,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.metric import Metric


if TYPE_CHECKING:
    from .postgres_metric_repository import PostgresMetricRepository


async def _get_metric(
    self: PostgresMetricRepository,
    company_id: CompanyId,
    *args: object,
    **kwargs: object,
) -> Metric | None:
    company = _company(company_id)
    values: dict[str, Any] = dict(kwargs)
    metric_id = _first(values, 'metric_id', 'id', 'metricId')
    if metric_id is None and args:
        metric_id = args[0]
    if metric_id is None:
        return None
    if self._session is None:
        return self._memory.get(company, {}).get(str(metric_id))
    await self._set_rls_context(company_id)
    result = await self._execute(
        f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id AND id = :metric_id',
        {'company_id': company, 'metric_id': str(metric_id)},
    )
    return _row_to_metric(await self._fetchone(result))
