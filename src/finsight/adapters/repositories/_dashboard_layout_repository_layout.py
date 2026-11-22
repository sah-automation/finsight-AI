"""Private helpers for config defaults and id filtering of saved layouts.

The rules mirror ``_dashboard_layout_filter_ids`` in migration 0009: ids are
kept in their stored order, ids outside the caller's visible set are dropped,
and an empty result falls back to the filtered config default.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from finsight.domain.ports.dashboard_layout_repository import LayoutRecord, VisibleIds

CONTRACT_VERSION = 1


@dataclass(frozen=True)
class _LayoutContext:
    """Config and effective visible ids for one repository call."""

    _config: Any
    _visible: dict[str, list[str]]

    @property
    def config(self) -> Any:
        return self._config

    @property
    def visible(self) -> dict[str, list[str]]:
        return self._visible


def _field(item: Any, name: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(name)
    return getattr(item, name, None)


def _as_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    return [value]


def _as_strings(value: Any) -> list[str]:
    return [str(item) for item in _as_items(value)]


def _section(config: Any, name: str) -> Any:
    section = _field(config, name)
    if section is None:
        raise RuntimeError(f'{name} config is required by the layout repository')
    return section


def _known_ids(config: Any) -> tuple[list[str], list[str]]:
    codes = _field(_section(config, 'kpi'), 'codes')
    specs = _field(_section(config, 'charts'), 'specs')
    if codes is None or specs is None:
        raise RuntimeError(
            'kpi.codes and charts.specs config are required by the layout repository'
        )
    if isinstance(specs, Mapping):
        chart_ids = [str(key) for key in specs]
    else:
        chart_ids = [str(_field(spec, 'chart_id')) for spec in _as_items(specs)]
    return _as_strings(codes), chart_ids


def as_identifiers(layout: Any) -> tuple[list[str], list[dict[str, Any]]]:
    """Normalize a layout's identifier lists for filtering or JSON binding."""
    codes = _as_strings(_field(layout, 'kpi_codes'))
    charts = [
        {'chart_id': str(_field(chart, 'chart_id') or ''), 'span': _field(chart, 'span')}
        for chart in _as_items(_field(layout, 'charts'))
    ]
    return codes, charts


def config_default(config: Any) -> dict[str, Any]:
    """Return the config-defined layout as plain identifiers, failing if absent."""
    default = _field(_section(config, 'dashboard'), 'default_layout')
    if default is None:
        raise RuntimeError('dashboard.default_layout config is required by the layout repository')
    codes, charts = as_identifiers(default)
    return {'kpi_codes': codes, 'charts': charts}


def effective_visible_ids(config: Any, requested: VisibleIds | None) -> dict[str, list[str]]:
    """Intersect the caller's visible set with config-known identifiers."""
    known_codes, known_charts = _known_ids(config)
    if requested is None:
        return {'kpi_codes': known_codes, 'chart_ids': known_charts}
    asked_codes = set(_as_strings(_field(requested, 'kpi_codes')))
    asked_charts = set(_as_strings(_field(requested, 'chart_ids')))
    return {
        'kpi_codes': [code for code in known_codes if code in asked_codes],
        'chart_ids': [chart for chart in known_charts if chart in asked_charts],
    }


def context(config: Any, requested: VisibleIds | None) -> _LayoutContext:
    """Build the shared config/visibility context for one repository call."""
    if config is None:
        raise RuntimeError('config is required by the layout repository')
    return _LayoutContext(config, effective_visible_ids(config, requested))


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
        _json_list(_field(mapping, 'kpi_codes')),
        _json_list(_field(mapping, 'charts')),
        int(_field(mapping, 'version') or 0),
        _field(mapping, 'updated_at'),
    )
