"""Private helpers for config defaults and id filtering of saved layouts.

The rules mirror ``_dashboard_layout_filter_ids`` in migration 0009: ids are
kept in their stored order, ids outside the caller's visible set are dropped,
and an empty result falls back to the filtered config default.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from finsight.domain.ports.dashboard_layout_repository import LayoutRecord, VisibleIds

CONTRACT_VERSION = 1


class _LayoutContext:
    """Injected config and effective visible-id set for one repository call."""

    def __init__(self, config: Any, visible: dict[str, list[str]]) -> None:
        self.config = config
        self.visible = visible


def _value(item: Any, field: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(field)
    return getattr(item, field, None)


def _items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    return [value]


def _as_text(value: Any) -> list[str]:
    return [str(item) for item in _items(value)]


def _known_ids(config: Any) -> tuple[list[str], list[str]]:
    specs = _value(_value(config, 'charts'), 'specs') or {}
    if isinstance(specs, Mapping):
        chart_ids = [str(key) for key in specs]
    else:
        chart_ids = [str(_value(spec, 'chart_id')) for spec in _items(specs)]
    return _as_text(_value(_value(config, 'kpi'), 'codes')), chart_ids


def as_identifiers(layout: Any) -> tuple[list[str], list[dict[str, Any]]]:
    """Normalize a layout's identifier lists for filtering or JSON binding."""
    codes = _as_text(_value(layout, 'kpi_codes'))
    charts = [
        {'chart_id': str(_value(chart, 'chart_id') or ''), 'span': _value(chart, 'span')}
        for chart in _items(_value(layout, 'charts'))
    ]
    return codes, charts


def config_default(config: Any) -> dict[str, Any]:
    """Return the config-defined layout as plain identifiers, failing if absent."""
    default = _value(_value(config, 'dashboard'), 'default_layout')
    if default is None:
        raise RuntimeError('dashboard.default_layout config is required by the layout repository')
    codes, charts = as_identifiers(default)
    return {'kpi_codes': codes, 'charts': charts}


def visible_ids(config: Any, requested: VisibleIds | None) -> dict[str, list[str]]:
    """Intersect the caller's visible set with config-known identifiers."""
    known_codes, known_charts = _known_ids(config)
    if requested is None:
        return {'kpi_codes': known_codes, 'chart_ids': known_charts}
    asked_codes = set(_as_text(_value(requested, 'kpi_codes')))
    asked_charts = set(_as_text(_value(requested, 'chart_ids')))
    return {
        'kpi_codes': [code for code in known_codes if code in asked_codes],
        'chart_ids': [chart for chart in known_charts if chart in asked_charts],
    }


def filter_layout(layout: Any, visible: Mapping[str, list[str]]) -> dict[str, list[Any]]:
    """Drop ids outside the visible set, preserving their stored order."""
    codes, charts = as_identifiers(layout)
    allowed_codes = set(visible.get('kpi_codes', []))
    allowed_charts = set(visible.get('chart_ids', []))
    return {
        'kpi_codes': [code for code in codes if code in allowed_codes],
        'charts': [chart for chart in charts if chart['chart_id'] in allowed_charts],
    }


def resolve_layout(
    layout: Any, config: Any, visible: Mapping[str, list[str]]
) -> dict[str, list[Any]]:
    """Filter ids, falling back to the filtered config default when nothing remains."""
    filtered = filter_layout(layout, visible)
    if filtered['kpi_codes'] or filtered['charts']:
        return filtered
    return filter_layout(config_default(config), visible)


def record(kpi_codes: list[Any], charts: list[Any], version: int, updated_at: Any) -> LayoutRecord:
    """Build the plain layout record returned by the port."""
    return {
        'contract_version': CONTRACT_VERSION,
        'kpi_codes': kpi_codes,
        'charts': charts,
        'version': version,
        'updated_at': updated_at,
    }


def default_record(config: Any, visible: Mapping[str, list[str]]) -> LayoutRecord:
    """Build the version-0 config default without touching storage."""
    filtered = filter_layout(config_default(config), visible)
    return record(filtered['kpi_codes'], filtered['charts'], 0, None)


def context(config: Any, requested: VisibleIds | None) -> _LayoutContext:
    """Build the shared config/visibility context for one repository call."""
    return _LayoutContext(config, visible_ids(config, requested))


def now() -> datetime:
    """Return the timestamp stored on a successful save."""
    return datetime.now(UTC)


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    return list(value or [])


def row_to_record(row: Any) -> LayoutRecord:
    """Convert a ``dashboard_layout_*`` result row into a plain layout record."""
    mapping = getattr(row, '_mapping', row)
    if not isinstance(mapping, Mapping):
        mapping = dict(mapping)
    return record(
        _json_list(_value(mapping, 'kpi_codes')),
        _json_list(_value(mapping, 'charts')),
        int(_value(mapping, 'version') or 0),
        _value(mapping, 'updated_at'),
    )
