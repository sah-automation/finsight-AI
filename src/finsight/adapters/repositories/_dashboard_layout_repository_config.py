"""Validate injected dashboard config and resolve its layout-owned values.

This module owns config defaults, the config catalogue of known ids and the
intersection of that catalogue with a caller's visible id set.
"""

from __future__ import annotations

from typing import Any

from finsight.domain.value_objects.layout_chart import LayoutChart
from finsight.domain.value_objects.layout_record import LayoutRecord
from finsight.domain.value_objects.visible_ids import VisibleIds

from ._dashboard_layout_repository_fields import CONTRACT_VERSION
from ._dashboard_layout_repository_visibility import visible_json_fields


def _field(value: Any, name: str) -> Any:
    found = getattr(value, name, None)
    if found is None:
        raise ValueError(f'{name} is required by the layout repository')
    return found


def default_fields(config: Any) -> dict[str, list[Any]]:
    """Return the injected config default as JSON-bound identifier lists."""
    default = _field(_field(config, 'dashboard'), 'default_layout')
    return {
        'kpi_codes': [str(code) for code in _field(default, 'kpi_codes')],
        'charts': [
            {'chart_id': str(chart.chart_id), 'span': str(chart.span)}
            for chart in _field(default, 'charts')
        ],
    }


def known_ids(config: Any) -> tuple[frozenset[str], frozenset[str]]:
    """Return the config catalogue of KPI codes and chart ids."""
    codes = _field(_field(config, 'kpi'), 'codes')
    specs = _field(_field(config, 'charts'), 'specs')
    return (
        frozenset(str(code) for code in codes),
        frozenset(str(chart_id) for chart_id in specs),
    )


def validate_config(config: Any) -> None:
    """Fail at construction when config lacks a default or catalogue."""
    if config is None:
        raise ValueError('config is required by the layout repository')
    dashboard = getattr(config, 'dashboard', None)
    if dashboard is None or getattr(dashboard, 'default_layout', None) is None:
        raise ValueError('dashboard.default_layout is required by the layout repository')
    default_fields(config)
    known_ids(config)


def effective_visible_ids(config: Any, requested: VisibleIds) -> VisibleIds:
    """Intersect caller visibility with config-known ids; never widen it."""
    codes, charts = known_ids(config)
    return VisibleIds(
        tuple(code for code in requested.kpi_codes if code in codes),
        tuple(chart for chart in requested.chart_ids if chart in charts),
    )


def default_record(config: Any, visible_ids: VisibleIds) -> LayoutRecord:
    """Build the visible config default at version 0 without touching storage."""
    fields = visible_json_fields(default_fields(config), visible_ids)
    return LayoutRecord(
        CONTRACT_VERSION,
        tuple(fields['kpi_codes']),
        tuple(LayoutChart(**chart) for chart in fields['charts']),
        0,
        None,
    )
