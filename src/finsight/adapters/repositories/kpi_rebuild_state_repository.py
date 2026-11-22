"""Postgres/Neon adapter for the global KPI rebuild-state gate.

The ``kpi_rebuild_state`` table is global (no RLS), keyed by
``computation_rule_version``. Writes never downgrade a version and never commit:
the caller owns the surrounding transaction, as with the KPI repository. With
no wired session the adapter uses an in-memory seam for the contract suite.
"""

from __future__ import annotations

from typing import Any, cast

from finsight.domain.ports.kpi_rebuild_state import KpiRebuildState as KpiRebuildStatePort
from finsight.domain.ports.kpi_rebuild_state import KpiRebuildStateValue

from .base_repository import BaseRepository

_SELECT_STATE = """
SELECT state FROM kpi_rebuild_state WHERE computation_rule_version = :version
"""
_ENSURE_PENDING = """
INSERT INTO kpi_rebuild_state (computation_rule_version, state)
VALUES (:version, 'pending')
ON CONFLICT (computation_rule_version) DO NOTHING
"""
_MARK_RUNNING = """
INSERT INTO kpi_rebuild_state (computation_rule_version, state)
VALUES (:version, 'running')
ON CONFLICT (computation_rule_version) DO UPDATE
SET state = 'running', updated_at = now()
WHERE kpi_rebuild_state.state = 'pending'
"""
_MARK_COMPLETE = """
INSERT INTO kpi_rebuild_state (computation_rule_version, state)
VALUES (:version, 'complete')
ON CONFLICT (computation_rule_version) DO UPDATE
SET state = 'complete', updated_at = now()
"""
_SELECT_INCOMPLETE = """
SELECT computation_rule_version FROM kpi_rebuild_state
WHERE state <> 'complete'
ORDER BY computation_rule_version
"""


def _version(value: str) -> str:
    version = str(value).strip()
    if not version:
        raise ValueError('A computation rule version is required')
    return version


def _column(row: Any, index: int, name: str) -> Any:
    mapping = getattr(row, '_mapping', None)
    if mapping is not None:
        return mapping[name]
    if isinstance(row, (list, tuple)):
        return row[index]
    return getattr(row, name, None)


class KpiRebuildStateRepository(KpiRebuildStatePort, BaseRepository):
    """Global rebuild lifecycle store; SQL when wired, in-memory otherwise."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._memory: dict[str, KpiRebuildStateValue] = {}

    async def get(self, version: str) -> KpiRebuildStateValue | None:
        key = _version(version)
        if self._session is None:
            return self._memory.get(key)
        row = await self._fetchone(await self._raw_execute(_SELECT_STATE, {'version': key}))
        if row is None:
            return None
        state = _column(row, 0, 'state')
        return None if state is None else cast('KpiRebuildStateValue', str(state))

    async def is_complete(self, version: str) -> bool:
        return await self.get(version) == 'complete'

    async def ensure_pending(self, version: str) -> None:
        key = _version(version)
        if self._session is None:
            self._memory.setdefault(key, 'pending')
            return
        await self._raw_execute(_ENSURE_PENDING, {'version': key})

    async def mark_running(self, version: str) -> None:
        key = _version(version)
        if self._session is None:
            if self._memory.get(key) in (None, 'pending'):
                self._memory[key] = 'running'
            return
        await self._raw_execute(_MARK_RUNNING, {'version': key})

    async def mark_complete(self, version: str) -> None:
        key = _version(version)
        if self._session is None:
            self._memory[key] = 'complete'
            return
        await self._raw_execute(_MARK_COMPLETE, {'version': key})

    async def incomplete_versions(self) -> list[str]:
        if self._session is None:
            return sorted(version for version, state in self._memory.items() if state != 'complete')
        rows = await self._fetchall(await self._raw_execute(_SELECT_INCOMPLETE))
        return [str(_column(row, 0, 'computation_rule_version')) for row in rows]
