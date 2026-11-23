"""Serialize dashboard layout value objects to and from storage fields."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from finsight.domain.value_objects.layout_chart import LayoutChart
from finsight.domain.value_objects.layout_record import LayoutRecord

if TYPE_CHECKING:
    from finsight.domain.value_objects.layout_draft import LayoutDraft

CONTRACT_VERSION = 1


def _field(value: Any, name: str) -> Any:
    found = value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)
    if found is None:
        raise ValueError(f'{name} is required by the layout repository')
    return found


def _optional_field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def json_fields(layout: LayoutDraft | LayoutRecord) -> dict[str, list[Any]]:
    """Normalize a layout value object into JSON-bound identifier lists."""
    return {
        'kpi_codes': list(layout.kpi_codes),
        'charts': [chart.to_mapping() for chart in layout.charts],
    }


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
