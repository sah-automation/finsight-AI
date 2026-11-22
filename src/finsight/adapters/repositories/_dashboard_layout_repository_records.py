"""Translate dashboard layouts between domain records and storage payloads.

This module owns one job: converting config defaults, incoming payloads and
result rows into the immutable layout value objects and JSON shapes used by the
SQL adapter.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from finsight.domain.value_objects.layout_chart import LayoutChart
from finsight.domain.value_objects.layout_record import LayoutRecord

if TYPE_CHECKING:
    from finsight.domain.value_objects.visible_ids import VisibleIds

CONTRACT_VERSION = 1


def validate_config(config: Any) -> None:
    """Fail at construction when config cannot supply a default layout."""
    if config is None:
        raise ValueError('config is required by the layout repository')
    dashboard = getattr(config, 'dashboard', None)
    if dashboard is None or getattr(dashboard, 'default_layout', None) is None:
        raise ValueError('dashboard.default_layout is required by the layout repository')
    _config_fields(config)


def _field(value: Any, name: str) -> Any:
    found = value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)
    if found is None:
        raise ValueError(f'{name} is required by the layout repository')
    return found


def _optional_field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def _chart_mapping(chart: Any) -> dict[str, Any]:
    if isinstance(chart, LayoutChart):
        return chart.to_mapping()
    return {
        'chart_id': str(_field(chart, 'chart_id')),
        'span': str(_field(chart, 'span')),
    }


def _config_fields(config: Any) -> dict[str, list[Any]]:
    default = _field(_field(config, 'dashboard'), 'default_layout')
    return {
        'kpi_codes': [str(code) for code in _field(default, 'kpi_codes')],
        'charts': [_chart_mapping(chart) for chart in _field(default, 'charts')],
    }


def json_fields(layout: Mapping[str, Any] | LayoutRecord) -> dict[str, list[Any]]:
    """Normalize an incoming layout into JSON-bound identifier lists."""
    if isinstance(layout, LayoutRecord):
        return {
            'kpi_codes': list(layout.kpi_codes),
            'charts': [chart.to_mapping() for chart in layout.charts],
        }
    return {
        'kpi_codes': [str(code) for code in _field(layout, 'kpi_codes')],
        'charts': [_chart_mapping(chart) for chart in _field(layout, 'charts')],
    }


def visible_json_fields(
    fields: Mapping[str, list[Any]], visible_ids: VisibleIds
) -> dict[str, list[Any]]:
    """Drop ids outside the caller's visible set, preserving stored order."""
    allowed_codes = set(visible_ids.kpi_codes)
    allowed_charts = set(visible_ids.chart_ids)
    return {
        'kpi_codes': [code for code in fields['kpi_codes'] if code in allowed_codes],
        'charts': [chart for chart in fields['charts'] if chart['chart_id'] in allowed_charts],
    }


def _record(fields: Mapping[str, list[Any]], version: int, updated_at: Any) -> LayoutRecord:
    return LayoutRecord(
        CONTRACT_VERSION,
        tuple(str(code) for code in fields['kpi_codes']),
        tuple(
            LayoutChart(str(chart['chart_id']), str(chart['span'])) for chart in fields['charts']
        ),
        version,
        updated_at,
    )


def default_record(config: Any, visible_ids: VisibleIds) -> LayoutRecord:
    """Build the visible config default at version 0 without touching storage."""
    return _record(visible_json_fields(_config_fields(config), visible_ids), 0, None)


def filter_record(record: LayoutRecord, visible_ids: VisibleIds) -> LayoutRecord:
    """Return only the ids the caller may see, keeping version and timestamp."""
    fields = visible_json_fields(json_fields(record), visible_ids)
    return replace(
        record,
        kpi_codes=tuple(fields['kpi_codes']),
        charts=tuple(LayoutChart(**chart) for chart in fields['charts']),
    )


def resolve_record(
    stored: LayoutRecord, default: LayoutRecord, visible_ids: VisibleIds
) -> LayoutRecord:
    """Fall back to the config default when filtering empties a stored layout."""
    filtered = filter_record(stored, visible_ids)
    if filtered.kpi_codes or filtered.charts:
        return replace(filtered, version=stored.version, updated_at=stored.updated_at)
    return replace(default, version=stored.version, updated_at=stored.updated_at)


def _json_list(value: Any) -> list[Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise TypeError('layout JSONB columns must contain arrays')
    return parsed


def from_row(row: Any) -> LayoutRecord:
    """Convert a ``dashboard_layout_*`` result row into a layout record."""
    mapping = getattr(row, '_mapping', row)
    if not isinstance(mapping, Mapping):
        mapping = dict(mapping)
    charts = _json_list(_field(mapping, 'charts'))
    return LayoutRecord(
        int(_field(mapping, 'contract_version')),
        tuple(str(code) for code in _json_list(_field(mapping, 'kpi_codes'))),
        tuple(
            LayoutChart(str(_field(chart, 'chart_id')), str(_field(chart, 'span')))
            for chart in charts
        ),
        int(_field(mapping, 'version')),
        _optional_field(mapping, 'updated_at'),
    )
