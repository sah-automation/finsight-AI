"""Shared helpers for PostgresMetricRepository."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from typing import Any

from finsight.domain.entities.metric import Metric

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


class _Filters:
    """Normalised, additive metric filters shared by memory and SQL paths."""

    def __init__(
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
