"""Contract tests for the saved dashboard layout repository port.

A database-free fake in the test tree exercises the shared port contract. The
production adapter is SQL-only and is covered separately by
``tests/unit/adapters/test_dashboard_layout_repository_sql.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.core.types import CompanyId, UserId
from finsight.domain.ports.dashboard_layout_repository import (
    LayoutChart,
    LayoutConflictError,
    VisibleIds,
)
from tests.support.dashboard_layout import (
    InMemoryDashboardLayoutRepository as DashboardLayoutRepository,
)
from tests.support.dashboard_layout import config, default_record, layout, visible_all

if TYPE_CHECKING:
    from finsight.domain.ports.dashboard_layout_repository import (
        DashboardLayoutRepository as DashboardLayoutRepositoryPort,
    )

pytestmark = pytest.mark.contract

COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000001')
OTHER_COMPANY = CompanyId('7e1a0000-0000-4000-8000-000000000002')
USER = UserId('8e1a0000-0000-4000-8000-000000000001')
OTHER_USER = UserId('8e1a0000-0000-4000-8000-000000000002')


@pytest.fixture
def repository() -> DashboardLayoutRepositoryPort:
    return DashboardLayoutRepository(config=config())


class TestDashboardLayoutRepositoryContract:
    async def test_get_layout_returns_config_default_on_miss_without_writing(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        first = await repository.get_layout(COMPANY, USER, visible_ids=visible_all())
        second = await repository.get_layout(COMPANY, USER, visible_ids=visible_all())

        assert first == default_record()
        assert second == default_record()
        assert repository._storage == {}

    async def test_get_layout_is_company_and_user_scoped(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        saved = await repository.save_layout(
            COMPANY, USER, layout(('cash_flow',)), 0, visible_ids=visible_all()
        )

        assert saved.version == 1
        assert (
            await repository.get_layout(OTHER_COMPANY, USER, visible_ids=visible_all())
            == default_record()
        )
        assert (
            await repository.get_layout(COMPANY, OTHER_USER, visible_ids=visible_all())
            == default_record()
        )

    async def test_save_layout_creates_first_version_then_increments(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        first = await repository.save_layout(
            COMPANY, USER, layout(('revenue', 'cash_flow')), 0, visible_ids=visible_all()
        )
        second = await repository.save_layout(
            COMPANY, USER, layout(('gross_margin',)), 1, visible_ids=visible_all()
        )

        assert first.version == 1
        assert first.kpi_codes == ('revenue', 'cash_flow')
        assert second.version == 2
        assert second.kpi_codes == ('gross_margin',)
        assert await repository.get_layout(COMPANY, USER, visible_ids=visible_all()) == second

    async def test_stale_save_raises_conflict_carrying_current_layout(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        await repository.save_layout(
            COMPANY, USER, layout(('revenue',)), 0, visible_ids=visible_all()
        )
        current = await repository.save_layout(
            COMPANY, USER, layout(('cash_flow',)), 1, visible_ids=visible_all()
        )

        with pytest.raises(LayoutConflictError) as conflict:
            await repository.save_layout(
                COMPANY, USER, layout(('burn_rate',)), 0, visible_ids=visible_all()
            )

        assert conflict.value.message == 'layout changed elsewhere'
        assert conflict.value.code == 'layout_changed'
        assert conflict.value.current_layout == current

    async def test_delete_layout_returns_to_config_default(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        await repository.save_layout(
            COMPANY, USER, layout(('revenue',)), 0, visible_ids=visible_all()
        )

        await repository.delete_layout(COMPANY, USER)

        assert (
            await repository.get_layout(COMPANY, USER, visible_ids=visible_all())
            == default_record()
        )

    async def test_delete_layout_does_not_touch_another_tenant(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        await repository.save_layout(
            COMPANY, USER, layout(('revenue',)), 0, visible_ids=visible_all()
        )
        other = await repository.save_layout(
            OTHER_COMPANY, USER, layout(('cash_flow',)), 0, visible_ids=visible_all()
        )

        await repository.delete_layout(COMPANY, USER)

        assert await repository.get_layout(OTHER_COMPANY, USER, visible_ids=visible_all()) == other

    async def test_invisible_and_unknown_ids_are_dropped_on_read_and_save(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        visible = VisibleIds(('revenue',), ('revenue_trend',))
        incoming = layout(
            ('revenue', 'burn_rate'),
            (
                ('revenue_trend', 'full'),
                ('not_in_config', 'half'),
            ),
        )

        saved = await repository.save_layout(COMPANY, USER, incoming, 0, visible_ids=visible)
        loaded = await repository.get_layout(COMPANY, USER, visible_ids=visible)

        assert saved.kpi_codes == ('revenue',)
        assert saved.charts == (LayoutChart('revenue_trend', 'full'),)
        assert loaded == saved

    async def test_visible_ids_is_mandatory(
        self, repository: DashboardLayoutRepositoryPort
    ) -> None:
        with pytest.raises(TypeError):
            await repository.get_layout(COMPANY, USER)  # type: ignore[call-arg]
