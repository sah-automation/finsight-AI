"""Auto-extracted helper for PostgresMetricRepository.list_metrics."""

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
    _Filters,
    _rows_to_metrics,
)

if TYPE_CHECKING:
    from finsight.core.types import CompanyId
    from finsight.domain.entities.metric import Metric


if TYPE_CHECKING:
    from .postgres_metric_repository import PostgresMetricRepository


async def _list_metrics(
    self: PostgresMetricRepository,
    company_id: CompanyId,
    *args: object,
    **kwargs: object,
) -> list[Metric]:
    company = _company(company_id)
    values: dict[str, Any] = dict(kwargs)
    if args and isinstance(args[0], dict):
        values = {**args[0], **values}
    filters = _Filters.from_values(values)
    if self._session is None:
        return self._list_memory(company, filters)
    await self._set_rls_context(company_id)
    params: dict[str, Any] = {'company_id': company}
    sql = f'SELECT {_RETURNING} FROM {_TABLE} WHERE company_id = :company_id'
    sql += filters.to_sql(params)
    sql += ' ORDER BY period_end DESC NULLS LAST, name ASC, id ASC'
    if filters.limit is not None:
        sql += ' LIMIT :limit'
        params['limit'] = filters.limit
    result = await self._execute(sql, params)
    return _rows_to_metrics(await self._fetchall(result))
