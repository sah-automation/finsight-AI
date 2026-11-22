"""Shared fixtures and a database-free fake for dashboard layout tests.

The fake implements the real port but lives only in the test tree, so the
production adapter has a single store path: the relational layout table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from finsight.adapters.repositories import _dashboard_layout_repository_records as records
from finsight.domain.ports.dashboard_layout_repository import (
    DashboardLayoutRepository as DashboardLayoutRepositoryPort,
)
from finsight.domain.ports.dashboard_layout_repository import (
    LayoutChart,
    LayoutConflictError,
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
    """Build the injected config slice the adapter validates at construction."""
    default = SimpleNamespace(
        kpi_codes=list(DEFAULT_CODES),
        charts=[SimpleNamespace(chart_id=chart_id, span=span) for chart_id, span in DEFAULT_CHARTS],
    )
    return SimpleNamespace(dashboard=SimpleNamespace(default_layout=default))


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
) -> Mapping[str, Any]:
    """Build an incoming layout payload."""
    selected = DEFAULT_CHARTS if charts is None else charts
    return {
        'contract_version': 1,
        'kpi_codes': list(DEFAULT_CODES if codes is None else codes),
        'charts': [{'chart_id': chart_id, 'span': span} for chart_id, span in selected],
    }


class InMemoryDashboardLayoutRepository(DashboardLayoutRepositoryPort):
    """Test-only port implementation backed by a per-instance dictionary."""

    def __init__(self, config: Any) -> None:
        self._config = config
        self._storage: dict[tuple[str, str], LayoutRecord] = {}

    @staticmethod
    def _key(company_id: Any, user_id: Any) -> tuple[str, str]:
        return (str(company_id), str(user_id))

    async def get_layout(
        self,
        company_id: Any,
        user_id: Any,
        *,
        visible_ids: VisibleIds,
    ) -> LayoutRecord:
        stored = self._storage.get(self._key(company_id, user_id))
        default = records.default_record(self._config, visible_ids)
        if stored is None:
            return default
        return records.resolve_record(stored, default, visible_ids)

    async def save_layout(
        self,
        company_id: Any,
        user_id: Any,
        layout: Mapping[str, Any] | LayoutRecord,
        expected_version: int,
        *,
        visible_ids: VisibleIds,
    ) -> LayoutRecord:
        key = self._key(company_id, user_id)
        stored = self._storage.get(key)
        default = records.default_record(self._config, visible_ids)
        current_version = 0 if stored is None else stored.version
        if current_version != expected_version:
            current = (
                default if stored is None else records.resolve_record(stored, default, visible_ids)
            )
            raise LayoutConflictError(current)

        filtered = records.filter_payload(records.as_payload(layout), visible_ids)
        if not filtered['kpi_codes'] and not filtered['charts']:
            filtered = records.as_payload(default)
        saved = LayoutRecord(
            1,
            tuple(filtered['kpi_codes']),
            tuple(LayoutChart(**chart) for chart in filtered['charts']),
            current_version + 1,
            datetime.now(UTC),
        )
        self._storage[key] = saved
        return saved

    async def delete_layout(self, company_id: Any, user_id: Any) -> None:
        self._storage.pop(self._key(company_id, user_id), None)
