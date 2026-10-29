"""Aurora/Postgres metric repository implementing the MetricRepository port.

Every statement names ``company_id`` first so the partitioned table is pruned to
one tenant partition and RLS applies as a second lock. Read filters are additive:
period, category, document and document version can be combined in one call.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import date
from typing import TYPE_CHECKING, Any

from finsight.domain.entities.metric import Metric
from finsight.domain.ports.metric_repository import MetricRepository as MetricRepositoryPort

from .base_repository import BaseRepository

if TYPE_CHECKING:
    from finsight.core.types import CompanyId

_TABLE = 'metrics'
_RETURNING = (
    'id, company_id, document_id, name, value, unit, currency, period_start, '
    'period_end, period_label, category, version_id, source_page, source_table, '
    'source_chunk_id, source_location, created_at, updated_at'
)


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first(values: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if values.get(name) is not None:
            return values.get(name)
    return default


def _as_filter_list(value: object) -> list[Any]:
    """Filter values treat a bare string as a single item, not an iterable."""
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _company(company_id: object) -> str:
    value = _text(company_id)
    if value is None:
        raise ValueError('company_id is required for metric queries')
    return value


def _json_value(value: object) -> object:
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)


def _row_value(row: object, *names: str) -> object:
    mapping = getattr(row, '_mapping', None)
    if mapping is None and isinstance(row, dict):
        mapping = row
    if mapping is not None:
        for name in names:
            try:
                if name in mapping:
                    return mapping[name]
            except TypeError:
                continue
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _period_label(period: object) -> str | None:
    if period is None:
        return None
    label = getattr(period, 'label', None)
    if label is not None:
        return str(label)
    return _text(period)


def _period_bounds(period: object) -> tuple[date | None, date | None]:
    if period is None:
        return None, None
    start = getattr(period, 'start_date', None)
    end = getattr(period, 'end_date', None)
    if isinstance(start, date) and isinstance(end, date):
        return start, end
    label = _text(period)
    if label is None:
        return None, None
    try:
        parsed = date.fromisoformat(label)
    except ValueError:
        return None, None
    return parsed, parsed


def _row_to_metric(row: object | None) -> Metric | None:
    if row is None:
        return None
    period = _period_label(_row_value(row, 'period_label', 'period'))
    if period is None:
        period = _period_label(_row_value(row, 'period_start'))
    source_location = _row_value(row, 'source_location')
    if isinstance(source_location, str):
        try:
            source_location = json.loads(source_location)
        except (TypeError, ValueError):
            source_location = None
    return Metric(
        metric_id=_row_value(row, 'id', 'metric_id'),
        company_id=_row_value(row, 'company_id'),
        name=_row_value(row, 'name'),
        value=_row_value(row, 'value'),
        unit=_row_value(row, 'unit'),
        currency=_row_value(row, 'currency'),
        period=period,
        document_id=_row_value(row, 'document_id'),
        version_id=_row_value(row, 'version_id', 'document_version'),
        category=_row_value(row, 'category'),
        source_location=source_location,
        source_page=_row_value(row, 'source_page', 'page_number'),
        source_table=_row_value(row, 'source_table', 'table_id'),
        source_chunk_id=_row_value(row, 'source_chunk_id', 'chunk_id'),
        created_at=_row_value(row, 'created_at'),
        updated_at=_row_value(row, 'updated_at'),
    )


def _rows_to_metrics(rows: object) -> list[Metric]:
    metrics: list[Metric] = []
    if not isinstance(rows, Iterable):
        return metrics
    for row in rows:
        metric = _row_to_metric(row)
        if metric is not None:
            metrics.append(metric)
    return metrics


def _metric_params(company_id: str, metric: Metric) -> dict[str, Any]:
    if str(metric.company_id) != company_id:
        raise ValueError('metric company_id must match the repository tenant')
    start, end = _period_bounds(metric.period)
    return {
        'id': str(metric.metric_id),
        'company_id': company_id,
        'document_id': _text(metric.document_id),
        'name': _text(metric.name),
        'value': metric.value,
        'unit': _text(metric.unit),
        'currency': _text(metric.currency),
        'period_start': start,
        'period_end': end,
        'period_label': _period_label(metric.period),
        'category': _text(metric.category),
        'version_id': _text(metric.version_id),
        'source_page': metric.source_page,
        'source_table': _text(metric.source_table),
        'source_chunk_id': _text(metric.source_chunk_id),
        'source_location': _json_value(metric.source_location),
    }


def _upsert_sql() -> str:
    columns = [
        'id',
        'company_id',
        'document_id',
        'name',
        'value',
        'unit',
        'currency',
        'period_start',
        'period_end',
        'period_label',
        'category',
        'version_id',
        'source_page',
        'source_table',
        'source_chunk_id',
        'source_location',
    ]
    updates = [f'{column} = EXCLUDED.{column}' for column in columns if column not in {'id'}]
    return (
        f'INSERT INTO {_TABLE} ({", ".join(columns)}) '
        f'VALUES ({", ".join(":" + column for column in columns)}) '
        'ON CONFLICT (id, company_id) DO UPDATE SET ' + ', '.join(updates) + ', updated_at = now() '
        f'WHERE {_TABLE}.company_id = EXCLUDED.company_id '
        f'RETURNING {_RETURNING}'
    )


class PostgresMetricRepository(MetricRepositoryPort, BaseRepository):
    """Read structured finance metrics with tenant-scoped filters.

    When constructed without a session the adapter keeps state in memory for
    contract tests and the pilot composition path. A wired session always uses
    SQL and RLS.
    """

    def __init__(self, session: Any | None = None, **kwargs: Any) -> None:
        super().__init__(session, **kwargs)
        self._memory: dict[str, dict[str, Metric]] = {}

    async def upsert_metric(
        self,
        company_id: CompanyId,
        metric: Metric,
        **kwargs: object,
    ) -> Metric:
        saved = await self.upsert_metrics(company_id, [metric], **kwargs)
        return saved[0] if saved else metric

    async def upsert_metrics(
        self,
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

    async def get_metric(
        self,
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

    async def list_metrics(
        self,
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

    def _upsert_memory(self, company: str, metrics: Sequence[Metric]) -> list[Metric]:
        store = self._memory.setdefault(company, {})
        saved: list[Metric] = []
        for metric in metrics:
            if str(metric.company_id) != company:
                raise ValueError('metric company_id must match the repository tenant')
            store[str(metric.metric_id)] = metric
            saved.append(metric)
        return saved

    def _list_memory(self, company: str, filters: _Filters) -> list[Metric]:
        metrics = list(self._memory.get(company, {}).values())
        selected = [metric for metric in metrics if filters.matches(metric)]
        selected.sort(
            key=lambda metric: (_period_sort_key(metric), str(metric.name), str(metric.metric_id))
        )
        if filters.limit is not None:
            return selected[: filters.limit]
        return selected


class _Filters:
    """Normalised, additive metric filters shared by memory and SQL paths."""

    def __init__(  # noqa: PLR0913 - each filter is an explicit scope dimension
        self,
        *,
        periods: list[str],
        categories: list[str],
        document_ids: list[str],
        version_ids: list[str],
        names: list[str],
        limit: int | None,
    ) -> None:
        self.periods = periods
        self.categories = categories
        self.document_ids = document_ids
        self.version_ids = version_ids
        self.names = names
        self.limit = limit

    @classmethod
    def from_values(cls, values: dict[str, Any]) -> _Filters:
        period = _first(values, 'period', 'fiscal_period', 'reporting_period')
        category = _first(values, 'category')
        categories = _first(values, 'categories', 'allowed_categories')
        document_id = _first(values, 'document_id')
        document_ids = _first(values, 'document_ids', 'documents')
        version_id = _first(values, 'version_id', 'document_version', 'document_version_id')
        version_ids = _first(values, 'version_ids', 'versions')
        name = _first(values, 'name', 'metric_name')
        names = _first(values, 'names', 'metric_names')
        limit = _first(values, 'limit', 'top_k')
        return cls(
            periods=[str(item) for item in _as_filter_list(period)],
            categories=[
                str(item) for item in _as_filter_list(categories) + _as_filter_list(category)
            ],
            document_ids=[
                str(item) for item in _as_filter_list(document_ids) + _as_filter_list(document_id)
            ],
            version_ids=[
                str(item) for item in _as_filter_list(version_ids) + _as_filter_list(version_id)
            ],
            names=[str(item) for item in _as_filter_list(names) + _as_filter_list(name)],
            limit=int(limit) if limit is not None else None,
        )

    def to_sql(self, params: dict[str, Any]) -> str:
        clauses: list[str] = []
        if self.periods:
            clauses.append(
                '(period_label = ANY(:periods) OR period_start::text = ANY(:periods) '
                'OR period_end::text = ANY(:periods))'
            )
            params['periods'] = self.periods
        if self.categories:
            clauses.append('category = ANY(:categories)')
            params['categories'] = self.categories
        if self.document_ids:
            clauses.append('document_id::text = ANY(:document_ids)')
            params['document_ids'] = self.document_ids
        if self.version_ids:
            clauses.append('version_id = ANY(:version_ids)')
            params['version_ids'] = self.version_ids
        if self.names:
            clauses.append('name = ANY(:names)')
            params['names'] = self.names
        return ''.join(f' AND {clause}' for clause in clauses)

    def matches(self, metric: Metric) -> bool:
        period = _period_label(metric.period)
        if self.periods and period not in self.periods:
            return False
        if self.categories and str(metric.category) not in self.categories:
            return False
        if self.document_ids and str(metric.document_id) not in self.document_ids:
            return False
        if self.version_ids and str(metric.version_id) not in self.version_ids:
            return False
        return not (self.names and str(metric.name) not in self.names)


def _period_sort_key(metric: Metric) -> str:
    label = _period_label(metric.period)
    return '' if label is None else label


# Naming variants used across the project.
AuroraMetricRepository = PostgresMetricRepository
PostgresMetricRepo = PostgresMetricRepository
MetricRepositoryAdapter = PostgresMetricRepository
RLSMetricRepository = PostgresMetricRepository

__all__ = [
    'AuroraMetricRepository',
    'MetricRepositoryAdapter',
    'PostgresMetricRepo',
    'PostgresMetricRepository',
    'RLSMetricRepository',
]
