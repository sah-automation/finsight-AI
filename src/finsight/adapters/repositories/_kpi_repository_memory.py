"""Private in-memory helpers for :class:`KpiRepository`.

The in-memory seam lets the shared contract suite exercise the public port
without a database. Selection, supersession and conflict rules mirror the
``kpi_current`` view in migration 0008.
"""

from __future__ import annotations

from typing import Any

KpiMemory = dict[str, dict[tuple[str, ...], dict[str, Any]]]

_STORAGE_KEY_FIELDS = (
    'company_id',
    'kpi_code',
    'period',
    'document_version_id',
    'chart_period',
)


def storage_key(row: dict[str, Any]) -> tuple[str, ...]:
    """Return the ADR-0009 storage key for a row."""
    return tuple(str(row.get(field, '')) for field in _STORAGE_KEY_FIELDS)


def upsert_rows(memory: KpiMemory, rows: list[dict[str, Any]], company_id: str) -> int:
    """Overwrite matching keys without ever deleting other rows."""
    tenant = memory.setdefault(company_id, {})
    for row in rows:
        tenant[storage_key(row)] = dict(row)
    return len(rows)


def _group_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get('kpi_code', '')),
        str(row.get('period', '')),
        str(row.get('chart_period', '')),
    )


def _rank(row: dict[str, Any]) -> tuple[int, str, str, str]:
    # Final beats draft; then newer version, update and version id win.
    is_final = 0 if row.get('document_status') == 'draft' else 1
    return (
        is_final,
        str(row.get('source_version_created_at') or ''),
        str(row.get('updated_at') or ''),
        str(row.get('document_version_id') or ''),
    )


def _signature(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (row.get('value'), row.get('currency'), row.get('units'))


def _has_conflict(ranked: list[dict[str, Any]]) -> bool:
    by_document: dict[str, tuple[Any, Any, Any]] = {}
    for row in ranked:
        if row.get('value') is None:
            continue
        document = str(row.get('document_id') or row.get('document_version_id', ''))
        signature = _signature(row)
        for other_document, other_signature in by_document.items():
            if other_document != document and other_signature != signature:
                return True
        by_document[document] = signature
    return False


def current_rows(memory: KpiMemory, company_id: str) -> list[dict[str, Any]]:
    """Reproduce the ``kpi_current`` selection/conflict rules in memory."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in memory.get(company_id, {}).values():
        if row.get('superseded_by_document_version_id') is not None:
            continue
        groups.setdefault(_group_key(row), []).append(dict(row))

    result: list[dict[str, Any]] = []
    for group in groups.values():
        ranked = sorted(group, key=_rank, reverse=True)
        selected = ranked[0]
        conflicted = _has_conflict(ranked)
        for row in ranked:
            if row is not selected and not conflicted:
                continue
            enriched = dict(row)
            enriched['is_selected'] = row is selected
            if conflicted:
                enriched['conflict_marker'] = f'{row["kpi_code"]}|{row["period"]}'
            else:
                enriched['conflict_marker'] = None
            result.append(enriched)
    return result


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item) for item in value]
    return [str(value)]


def _matches(row: dict[str, Any], criteria: dict[str, Any]) -> bool:
    codes = criteria['codes']
    if codes and row.get('kpi_code') not in codes:
        return False
    chart_periods = criteria['chart_periods']
    if chart_periods and row.get('chart_period') not in chart_periods:
        return False
    ranges = (
        ('period_start', criteria['period_from'], criteria['period_to']),
        ('chart_period_start', criteria['chart_from'], criteria['chart_to']),
    )
    for field, lower, upper in ranges:
        value = str(row.get(field, ''))
        if lower and value < str(lower):
            return False
        if upper and value > str(upper):
            return False
    version = criteria['document_version_id']
    if version and row.get('document_version_id') != version:
        return False
    return all(
        not criteria[field] or row.get(field) == criteria[field]
        for field in ('currency', 'units', 'computation_status')
    )


def apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply the additive, tenant-scoped filters accepted by ``get_current``."""
    criteria = {
        'codes': _as_list(filters.get('kpi_codes', filters.get('kpi_code'))),
        'chart_periods': _as_list(filters.get('chart_periods', filters.get('chart_period'))),
        'period_from': filters.get('period_from'),
        'period_to': filters.get('period_to'),
        'chart_from': filters.get('chart_period_from'),
        'chart_to': filters.get('chart_period_to'),
        'document_version_id': filters.get('document_version_id'),
        'currency': filters.get('currency'),
        'units': filters.get('units'),
        'computation_status': filters.get('computation_status'),
    }
    filtered = [row for row in rows if _matches(row, criteria)]
    limit = filters.get('limit')
    return filtered[: int(limit)] if limit is not None else filtered
