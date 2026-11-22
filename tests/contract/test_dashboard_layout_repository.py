"""Contract tests for the saved dashboard layout repository port.

The primary adapter is exercised through its in-memory seam so the shared
contract runs without a database. A wired session uses the same methods against
``dashboard_layouts`` through the read/save functions from migration 0009 with
RLS; both paths return the config default on a miss without writing a row.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from finsight.adapters.repositories.dashboard_layout_repository import DashboardLayoutRepository
from finsight.domain.ports.dashboard_layout_repository import LayoutConflictError

from finsight.core.types import CompanyId, UserId

if TYPE_CHECKING:
    from finsight.domain.ports.dashboard_layout_repository import (
        DashboardLayoutRepository as DashboardLayoutRepositoryPort,
    )

pytestmark = pytest.mark.contract

COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000001')
OTHER_COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000002')
USER = UserId('8e1a0000-0000-4000-8000-000000000001')
OTHER_USER = UserId('8e1a0000-0000-4000-8000-000000000002')

DEFAULT_CODES = ['revenue', 'gross_margin', 'net_margin']
DEFAULT_CHARTS = [
    {'chart_id': 'revenue_trend', 'span': 'full'},
    {'chart_id': 'margin_trend', 'span': 'half'},
]


def _config() -> Any:
    """Build the injected config slice the adapter resolves defaults from."""
    default = SimpleNamespace(
        kpi_codes=list(DEFAULT_CODES),
        charts=[SimpleNamespace(**chart) for chart in DEFAULT_CHARTS],
    )
    return SimpleNamespace(
        dashboard=SimpleNamespace(default_layout=default),
        kpi=SimpleNamespace(codes=(*DEFAULT_CODES, 'cash_flow')),
        charts=SimpleNamespace(specs={chart['chart_id']: object() for chart in DEFAULT_CHARTS}),
    )


def _default_layout() -> dict[str, Any]:
    return {
        'contract_version': 1,
        'kpi_codes': list(DEFAULT_CODES),
        'charts': [dict(chart) for chart in DEFAULT_CHARTS],
        'version': 0,
        'updated_at': None,
    }


def _layout(
    codes: list[str] | None = None, charts: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    return {
        'contract_version': 1,
        'kpi_codes': list(DEFAULT_CODES if codes is None else codes),
        'charts': [dict(chart) for chart in (DEFAULT_CHARTS if charts is None else charts)],
    }


@pytest.fixture
def repository() -> DashboardLayoutRepositoryPort:
    return DashboardLayoutRepository(config=_config())


class TestDashboardLayoutRepositoryContract:
    async def test_get_layout_returns_config_default_on_miss_without_writing(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        first = await repository.get_layout(COMPANY, USER)
        second = await repository.get_layout(COMPANY, USER)

        assert first == _default_layout()
        assert second == _default_layout()

    async def test_get_layout_is_company_and_user_scoped(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        saved = await repository.save_layout(COMPANY, USER, _layout(['cash_flow']), 0)

        assert saved['version'] == 1
        assert (await repository.get_layout(OTHER_COMPANY, USER)) == _default_layout()
        assert (await repository.get_layout(COMPANY, OTHER_USER)) == _default_layout()

    async def test_save_layout_creates_first_version_then_increments(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        first = await repository.save_layout(COMPANY, USER, _layout(['revenue', 'cash_flow']), 0)
        second = await repository.save_layout(COMPANY, USER, _layout(['gross_margin']), 1)

        assert first['version'] == 1
        assert first['kpi_codes'] == ['revenue', 'cash_flow']
        assert second['version'] == 2
        assert second['kpi_codes'] == ['gross_margin']
        assert (await repository.get_layout(COMPANY, USER)) == second

    async def test_stale_save_raises_conflict_carrying_current_layout(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        await repository.save_layout(COMPANY, USER, _layout(['revenue']), 0)
        current = await repository.save_layout(COMPANY, USER, _layout(['cash_flow']), 1)

        with pytest.raises(LayoutConflictError) as conflict:
            await repository.save_layout(COMPANY, USER, _layout(['burn_rate']), 0)

        assert conflict.value.message == 'layout changed elsewhere'
        assert conflict.value.current_layout == current

    async def test_delete_layout_returns_to_config_default(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        await repository.save_layout(COMPANY, USER, _layout(['revenue']), 0)

        await repository.delete_layout(COMPANY, USER)

        assert (await repository.get_layout(COMPANY, USER)) == _default_layout()

    async def test_delete_layout_does_not_touch_another_tenant(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        await repository.save_layout(COMPANY, USER, _layout(['revenue']), 0)
        other = await repository.save_layout(OTHER_COMPANY, USER, _layout(['cash_flow']), 0)

        await repository.delete_layout(COMPANY, USER)

        assert (await repository.get_layout(OTHER_COMPANY, USER)) == other

    async def test_invisible_and_unknown_ids_are_dropped_on_read_and_save(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        visible = {'kpi_codes': ['revenue'], 'chart_ids': ['revenue_trend']}
        layout = _layout(
            ['revenue', 'burn_rate'],
            [
                {'chart_id': 'revenue_trend', 'span': 'full'},
                {'chart_id': 'not_in_config', 'span': 'half'},
            ],
        )

        saved = await repository.save_layout(COMPANY, USER, layout, 0, visible_ids=visible)
        loaded = await repository.get_layout(COMPANY, USER, visible_ids=visible)

        assert saved['kpi_codes'] == ['revenue']
        assert saved['charts'] == [{'chart_id': 'revenue_trend', 'span': 'full'}]
        assert loaded == saved
