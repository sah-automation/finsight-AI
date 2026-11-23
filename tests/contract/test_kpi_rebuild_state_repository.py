"""Contract tests for the KPI rebuild-state port.

``kpi_rebuild_state`` gates a new ``computation_rule_version``: it starts
``pending``, moves through ``running`` and reaches ``complete`` only after
every company in the rolling rebuild succeeds. The primary adapter is
exercised through its in-memory seam so the shared contract runs without a
database; a wired session uses the same methods against the migration 0008
table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from finsight.adapters.repositories.kpi_rebuild_state_repository import (
    KpiRebuildStateRepository,
)

if TYPE_CHECKING:
    from finsight.domain.ports.kpi_rebuild_state import KpiRebuildState

pytestmark = pytest.mark.contract

VERSION = 'rules-v2'
OTHER_VERSION = 'rules-v3'


@pytest.fixture
def state() -> KpiRebuildState:
    return KpiRebuildStateRepository()


class TestKpiRebuildStateContract:
    async def test_unknown_version_is_not_complete(self, state: KpiRebuildState) -> None:
        assert await state.get(VERSION) is None
        assert await state.is_complete(VERSION) is False

    async def test_lifecycle_pending_running_complete(self, state: KpiRebuildState) -> None:
        await state.ensure_pending(VERSION)
        assert await state.get(VERSION) == 'pending'
        assert await state.is_complete(VERSION) is False

        await state.mark_running(VERSION)
        assert await state.get(VERSION) == 'running'
        assert await state.is_complete(VERSION) is False

        await state.mark_complete(VERSION)
        assert await state.get(VERSION) == 'complete'
        assert await state.is_complete(VERSION) is True

    async def test_ensure_pending_is_idempotent_and_never_downgrades(
        self, state: KpiRebuildState
    ) -> None:
        await state.ensure_pending(VERSION)
        await state.mark_running(VERSION)
        await state.ensure_pending(VERSION)
        assert await state.get(VERSION) == 'running'

        await state.mark_complete(VERSION)
        await state.ensure_pending(VERSION)
        assert await state.get(VERSION) == 'complete'

    async def test_state_transitions_create_missing_version(self, state: KpiRebuildState) -> None:
        await state.mark_running(VERSION)
        assert await state.get(VERSION) == 'running'
        await state.mark_complete(VERSION)
        assert await state.get(VERSION) == 'complete'

    async def test_incomplete_versions_are_scoped_and_stable(self, state: KpiRebuildState) -> None:
        await state.ensure_pending(VERSION)
        await state.mark_complete(OTHER_VERSION)
        assert await state.incomplete_versions() == [VERSION]

        await state.mark_complete(VERSION)
        assert await state.incomplete_versions() == []
