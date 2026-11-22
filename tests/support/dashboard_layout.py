"""Shared fixtures and a SQL-shape fake for dashboard layout tests.

The fake session answers the same SQL shapes as migration 0009's
``dashboard_layout_get``/``dashboard_layout_save`` functions, so the shared
contract runs through the production adapter without a database.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from finsight.domain.ports.dashboard_layout_repository import (
    LayoutChart,
    LayoutDraft,
    LayoutRecord,
    VisibleIds,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_CODES = ('revenue', 'gross_margin', 'net_margin')
KNOWN_CODES = (*DEFAULT_CODES, 'cash_flow', 'burn_rate')
DEFAULT_CHARTS = (
    ('revenue_trend', 'full'),
    ('margin_trend', 'half'),
)


def config() -> Any:
    """Build the injected config slices the adapter validates and filters by."""
    default = SimpleNamespace(
        kpi_codes=list(DEFAULT_CODES),
        charts=[SimpleNamespace(chart_id=chart_id, span=span) for chart_id, span in DEFAULT_CHARTS],
    )
    return SimpleNamespace(
        dashboard=SimpleNamespace(default_layout=default),
        kpi=SimpleNamespace(codes=KNOWN_CODES),
        charts=SimpleNamespace(specs={chart_id: object() for chart_id, _ in DEFAULT_CHARTS}),
    )


def visible_all() -> VisibleIds:
    """Return the full role-visible id set for the fixture config."""
    return VisibleIds(KNOWN_CODES, tuple(chart_id for chart_id, _ in DEFAULT_CHARTS))


def default_record() -> LayoutRecord:
    """Return the expected version-0 config default."""
    return LayoutRecord(
        1,
        DEFAULT_CODES,
        tuple(LayoutChart(chart_id, span) for chart_id, span in DEFAULT_CHARTS),
        0,
        None,
    )


def layout(
    codes: tuple[str, ...] | None = None,
    charts: tuple[tuple[str, str], ...] | None = None,
) -> LayoutDraft:
    """Build an incoming layout value object."""
    selected = DEFAULT_CHARTS if charts is None else charts
    return LayoutDraft(
        1,
        DEFAULT_CODES if codes is None else codes,
        tuple(LayoutChart(chart_id, span) for chart_id, span in selected),
    )


class _Result:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def fetchall(self) -> list[Any]:
        return self._rows


def _filter_fields(fields: Mapping[str, Any], visible: Mapping[str, Any]) -> dict[str, list[Any]]:
    allowed_codes = set(visible.get('kpi_codes', []))
    allowed_charts = set(visible.get('chart_ids', []))
    return {
        'kpi_codes': [code for code in fields['kpi_codes'] if code in allowed_codes],
        'charts': [chart for chart in fields['charts'] if chart['chart_id'] in allowed_charts],
    }


def _config_fields(config: Any) -> dict[str, list[Any]]:
    default = config.dashboard.default_layout
    return {
        'kpi_codes': list(default.kpi_codes),
        'charts': [{'chart_id': chart.chart_id, 'span': chart.span} for chart in default.charts],
    }


def _row(fields: Mapping[str, Any], version: int, updated_at: Any) -> dict[str, Any]:
    return {
        'contract_version': 1,
        'kpi_codes': json.dumps(fields['kpi_codes']),
        'charts': json.dumps(fields['charts']),
        'version': version,
        'updated_at': updated_at,
    }


class LayoutSqlSession:
    """Record statements and emulate migration 0009's layout SQL functions."""

    def __init__(self, config: Any) -> None:
        self._config = config
        self._rows: dict[tuple[str, str], dict[str, Any]] = {}
        self.statements: list[tuple[str, dict[str, Any]]] = []
        self.commits = 0

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        sql = str(statement)
        bound = dict(params or {})
        self.statements.append((sql, bound))
        if 'set_config' in sql:
            return _Result()
        if 'dashboard_layout_get' in sql:
            return self._get(bound)
        if 'dashboard_layout_save' in sql:
            return self._save(bound)
        if 'DELETE FROM dashboard_layouts' in sql:
            return self._delete(bound)
        raise AssertionError(f'unexpected SQL: {sql}')

    def _key(self, params: Mapping[str, Any]) -> tuple[str, str]:
        return (str(params['company_id']), str(params['user_id']))

    def _visible(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return json.loads(params['visible_ids'])

    def _get(self, params: Mapping[str, Any]) -> _Result:
        visible = self._visible(params)
        default = _filter_fields(_config_fields(self._config), visible)
        stored = self._rows.get(self._key(params))
        if stored is None:
            return _Result([_row(default, 0, None)])
        fields = _filter_fields(stored, visible)
        if not fields['kpi_codes'] and not fields['charts']:
            fields = default
        return _Result([_row(fields, stored['version'], stored['updated_at'])])

    def _save(self, params: Mapping[str, Any]) -> _Result:
        key = self._key(params)
        visible = self._visible(params)
        incoming = {
            'kpi_codes': json.loads(params['kpi_codes']),
            'charts': json.loads(params['charts']),
        }
        fields = _filter_fields(incoming, visible)
        if not fields['kpi_codes'] and not fields['charts']:
            fields = _filter_fields(_config_fields(self._config), visible)
        stored = self._rows.get(key)
        current_version = 0 if stored is None else int(stored['version'])
        if current_version != params['expected_version']:
            return _Result()
        updated_at = datetime.now(UTC)
        self._rows[key] = {**fields, 'version': current_version + 1, 'updated_at': updated_at}
        return _Result([_row(fields, current_version + 1, updated_at)])

    def _delete(self, params: Mapping[str, Any]) -> _Result:
        self._rows.pop(self._key(params), None)
        return _Result()

    def commit(self) -> None:
        self.commits += 1
