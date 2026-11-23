"""Private SQL-building helpers for the KPI repository.

Only whitelisted column names become SQL identifiers; every value stays a
bound parameter. ``kpi_current`` is the sole read surface.
"""

from __future__ import annotations

from typing import Any

_EQUALITY_COLUMNS = (
    ('kpi_code', 'kpi_code'),
    ('currency', 'currency'),
    ('units', 'units'),
    ('computation_status', 'computation_status'),
    ('document_version_id', 'document_version_id'),
    ('chart_period', 'chart_period'),
)
_RANGE_COLUMNS = (
    ('period_from', 'period_start'),
    ('period_to', 'period_start'),
    ('chart_period_from', 'chart_period_start'),
    ('chart_period_to', 'chart_period_start'),
)


def _add_in_clause(clauses: list[str], params: dict[str, Any], column: str, values: Any) -> None:
    if values is None or isinstance(values, str):
        return
    items = list(dict.fromkeys(str(item) for item in values))
    if not items:
        return
    placeholders = ', '.join(f':{column}_{index}' for index in range(len(items)))
    clauses.append(f'{column} IN ({placeholders})')
    for index, item in enumerate(items):
        params[f'{column}_{index}'] = item


def _add_equalities(clauses: list[str], params: dict[str, Any], values: dict[str, Any]) -> None:
    for key, column in _EQUALITY_COLUMNS:
        if values.get(key) is not None:
            clauses.append(f'{column} = :{key}')
            params[key] = values[key]
    _add_in_clause(clauses, params, 'kpi_code', values.get('kpi_codes'))
    _add_in_clause(clauses, params, 'chart_period', values.get('chart_periods'))


def _add_ranges(clauses: list[str], params: dict[str, Any], values: dict[str, Any]) -> None:
    for key, column in _RANGE_COLUMNS:
        if values.get(key) is None:
            continue
        operator = '>=' if key.endswith('_from') else '<='
        clauses.append(f'{column} {operator} :{key}')
        params[key] = values[key]


def build_select_sql(values: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return the parameterised ``kpi_current`` query and its bound values."""
    clauses = ['company_id = :company_id']
    params: dict[str, Any] = {'company_id': values['company_id']}
    _add_equalities(clauses, params, values)
    _add_ranges(clauses, params, values)

    where_clause = ' AND '.join(clauses)
    sql = (
        f'SELECT * FROM kpi_current WHERE {where_clause} '  # noqa: S608
        'ORDER BY period_start DESC, kpi_code, chart_period, document_version_id'
    )
    if values.get('limit') is not None:
        sql += ' LIMIT :limit'
        params['limit'] = int(values['limit'])
    return sql, params
